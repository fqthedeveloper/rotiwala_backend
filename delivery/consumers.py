# delivery/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DeliveryBoyProfile, DeliveryAssignment
from django.utils import timezone


class DeliveryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = None

        if self.user.role == 'delivery_boy':
            profile = await self.get_delivery_boy_profile(self.user)
            if profile:
                self.group_name = f'delivery_boy_{profile.id}'
        elif self.user.role == 'manager':
            profile = await self.get_manager_profile(self.user)
            if profile and profile.shop:
                self.group_name = f'shop_{profile.shop.id}_delivery'
        elif self.user.role == 'super_admin':
            self.group_name = 'admin_delivery'

        if not self.group_name:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Not used for now - server pushes events
        pass

    async def delivery_event(self, event):
        """Send delivery event to the client."""
        await self.send(text_data=json.dumps({
            'type': event['event_type'],
            'data': event['data'],
            'timestamp': event['timestamp'],
        }))

    @database_sync_to_async
    def get_delivery_boy_profile(self, user):
        try:
            return DeliveryBoyProfile.objects.get(user=user)
        except DeliveryBoyProfile.DoesNotExist:
            return None

    @database_sync_to_async
    def get_manager_profile(self, user):
        try:
            return user.manager_profile
        except:
            return None


# ============================================================
#  HELPER FUNCTIONS TO PUSH EVENTS
# ============================================================

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def send_delivery_event(group_name, event_type, data):
    """Send a delivery event to a WebSocket group."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'delivery_event',
            'event_type': event_type,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }
    )


def notify_delivery_assignment(assignment):
    """Notify the assigned delivery boy."""
    group = f'delivery_boy_{assignment.delivery_boy.id}'
    send_delivery_event(group, 'DELIVERY_ASSIGNED', {
        'assignment_id': assignment.id,
        'order_number': assignment.order.order_number,
        'customer_name': assignment.order.customer_name,
        'estimated_distance': str(assignment.estimated_distance_km) if assignment.estimated_distance_km else None,
    })


def notify_delivery_status_update(assignment):
    """Notify manager and admin about status changes."""
    # Notify shop group
    shop_group = f'shop_{assignment.shop.id}_delivery'
    send_delivery_event(shop_group, 'DELIVERY_STATUS_UPDATE', {
        'assignment_id': assignment.id,
        'status': assignment.status,
        'order_number': assignment.order.order_number,
        'delivery_boy': assignment.delivery_boy.full_name,
    })

    # Notify admin group
    send_delivery_event('admin_delivery', 'DELIVERY_STATUS_UPDATE', {
        'assignment_id': assignment.id,
        'status': assignment.status,
        'shop': assignment.shop.shop_code,
        'order_number': assignment.order.order_number,
        'delivery_boy': assignment.delivery_boy.full_name,
    })