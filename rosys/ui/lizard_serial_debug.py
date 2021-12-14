from nicegui.ui import Ui
from ..communication.communication import Communication
from ..communication.serial_communication import SerialCommunication
from .. import event


class LizardSerialDebug:
    ui: Ui = None  # will be set by rosys.ui.configure
    communication: Communication = None  # will be set by rosys.ui.configure

    def __init__(self) -> None:
        if not isinstance(self.communication, SerialCommunication):
            return
        self.ui.switch('Lizard', value=self.communication.serial.isOpen(), on_change=self.change)

    async def change(self, status):
        assert isinstance(self.communication, SerialCommunication)
        if status.value:
            self.communication.connect()
            await event.call(event.Id.NEW_NOTIFICATION, 'connected to Lizard')
        else:
            await event.call(event.Id.PAUSE_AUTOMATIONS, 'communication is deactivated')
            self.communication.disconnect()
            await event.call(event.Id.NEW_NOTIFICATION, 'disconnected from Lizard')
