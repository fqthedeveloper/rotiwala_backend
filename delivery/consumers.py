# delivery/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DeliveryBoyProfile, DeliveryAssignment
from django.utils import timezone
from urllib.parse import parse_qs


class DeliveryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = None
        self.order_group = None

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
        elif self.user.role == 'customer':
            # Customer may connect with ?order_id=123 to track that order
            query = parse_qs(self.scope['query_string'].decode())
            order_id = query.get('order_id', [None])[0]
            if order_id:
                self.order_group = f'order_{order_id}'
                self.group_name = self.order_group

        if not self.group_name and not self.order_group:
            await self.close()
            return

        if self.group_name:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        if self.order_group:
            await self.channel_layer.group_add(self.order_group, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.order_group:
            await self.channel_layer.group_discard(self.order_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'update_location':
            if self.user.role != 'delivery_boy':
                return
            profile = await self.get_delivery_boy_profile(self.user)
            if not profile:
                return
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            if latitude is not None and longitude is not None:
                await self.update_delivery_boy_location(profile.id, latitude, longitude)
                # Broadcast to shop and admin groups
                await self.channel_layer.group_send(
                    f'shop_{profile.shop_id}_delivery',
                    {
                        'type': 'delivery_event',
                        'event_type': 'BOY_LOCATION',
                        'data': {
                            'delivery_boy_id': profile.id,
                            'latitude': latitude,
                            'longitude': longitude,
                        },
                        'timestamp': timezone.now().isoformat(),
                    }
                )
                # Broadcast to all active order groups for this boy
                assignment_ids = await self.get_active_assignment_ids_for_boy(profile.id)
                for order_id in assignment_ids:
                    await self.channel_layer.group_send(
                        f'order_{order_id}',
                        {
                            'type': 'delivery_event',
                            'event_type': 'BOY_LOCATION',
                            'data': {
                                'delivery_boy_id': profile.id,
                                'latitude': latitude,
                                'longitude': longitude,
                            },
                            'timestamp': timezone.now().isoformat(),
                        }
                    )

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

    @database_sync_to_async
    def update_delivery_boy_location(self, boy_id, lat, lon):
        boy = DeliveryBoyProfile.objects.get(id=boy_id)
        boy.update_location(lat, lon)

    @database_sync_to_async
    def get_active_assignment_ids_for_boy(self, boy_id):
        assignments = DeliveryAssignment.objects.filter(
            delivery_boy_id=boy_id,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).values_list('order_id', flat=True)
        return list(assignments)


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