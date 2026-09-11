import json

from channels.generic.websocket import (
    AsyncWebsocketConsumer
)


class OrderConsumer(
    AsyncWebsocketConsumer
):

    async def connect(self):

        self.order_id = self.scope[
            "url_route"
        ]["kwargs"]["order_id"]

        self.room_group_name = (
            f"order_{self.order_id}"
        )

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        print(
            f"Customer Connected Order {self.order_id}"
        )

    async def disconnect(
        self,
        close_code
    ):

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        print(
            f"Customer Disconnected Order {self.order_id}"
        )

    async def receive(
        self,
        text_data
    ):
        pass

    async def order_update(
        self,
        event
    ):

        await self.send(
            text_data=json.dumps(
                event["data"]
            )
        )


class ManagerOrderConsumer(
    AsyncWebsocketConsumer
):

    async def connect(
        self
    ):

        self.room_group_name = (
            "manager_orders"
        )

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        print(
            "Manager Connected"
        )

    async def disconnect(
        self,
        close_code
    ):

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        print(
            "Manager Disconnected"
        )

    async def receive(
        self,
        text_data
    ):
        pass

    async def manager_order_update(
        self,
        event
    ):

        await self.send(
            text_data=json.dumps(
                event["data"]
            )
        )


class StaffOrderConsumer(
    AsyncWebsocketConsumer
):
    """
    WebSocket consumer for both Manager and Preparing Staff of a specific shop.
    """
    async def connect(self):
        self.shop_id = self.scope["url_route"]["kwargs"].get("shop_id")
        self.groups = ["manager_orders"]
        if self.shop_id:
            self.groups.append(f"shop_{self.shop_id}_staff")

        for grp in self.groups:
            await self.channel_layer.group_add(grp, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        for grp in getattr(self, "groups", []):
            await self.channel_layer.group_discard(grp, self.channel_name)

    async def receive(self, text_data):
        pass

    async def manager_order_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def staff_order_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class DisplayScreenConsumer(
    AsyncWebsocketConsumer
):
    """
    WebSocket consumer for the public / customer-facing TV display screen.
    Listens to shop_{shop_id}_display.
    """
    async def connect(self):
        self.shop_id = self.scope["url_route"]["kwargs"].get("shop_id")
        self.room_group_name = f"shop_{self.shop_id}_display"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        pass

    async def display_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def display_refresh(self, event):
        await self.send(text_data=json.dumps(event["data"]))