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