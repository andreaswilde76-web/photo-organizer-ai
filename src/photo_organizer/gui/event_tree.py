"""An editable, drag-and-drop event preview tree.

Top-level items are events; their children are the individual media files.
Users can:

* rename an event (double-click the event row),
* drag a file from one event onto another to **move** it (splitting/merging),
* drag an event row onto another event to **merge** the two events.

The widget keeps an in-memory list of :class:`Event` objects in sync so the main
window can rebuild the placement plan from the edited structure.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from ..models import Event, MediaFile

__all__ = ["EventTree"]

_EVENT_ROLE = Qt.ItemDataRole.UserRole
_FILE_ROLE = Qt.ItemDataRole.UserRole + 1


class EventTree(QTreeWidget):
    """Tree widget presenting events and their files with drag-and-drop edits."""

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderLabels(["Event / File", "Info"])
        self.setColumnCount(2)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)

    # -- population ------------------------------------------------------ #
    def set_events(self, events: list[Event]) -> None:
        """Populate the tree from *events*."""
        self.clear()
        for event in events:
            self.addTopLevelItem(self._make_event_item(event))
        self.expandToDepth(0)

    def _make_event_item(self, event: Event) -> QTreeWidgetItem:
        span = ""
        if event.start and event.end:
            span = event.start.strftime("%Y-%m-%d")
            if event.end.date() != event.start.date():
                span += f" - {event.end.strftime('%Y-%m-%d')}"
        item = QTreeWidgetItem([event.name, f"{event.size} files  {span}".strip()])
        item.setData(0, _EVENT_ROLE, event.event_id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDropEnabled)
        for media in event.files:
            item.addChild(self._make_file_item(media))
        return item

    @staticmethod
    def _make_file_item(media: MediaFile) -> QTreeWidgetItem:
        date = media.capture_date.strftime("%Y-%m-%d %H:%M") if media.capture_date else "no date"
        child = QTreeWidgetItem([media.path.name, date])
        child.setData(0, _FILE_ROLE, media)
        flags = child.flags()
        flags |= Qt.ItemFlag.ItemIsDragEnabled
        flags &= ~Qt.ItemFlag.ItemIsDropEnabled
        child.setFlags(flags)
        return child

    # -- read back ------------------------------------------------------- #
    def to_events(self) -> list[Event]:
        """Reconstruct the (possibly edited) list of :class:`Event` objects."""
        events: list[Event] = []
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item is None:
                continue
            files: list[MediaFile] = []
            for j in range(item.childCount()):
                child = item.child(j)
                if child is None:
                    continue
                media = child.data(0, _FILE_ROLE)
                if isinstance(media, MediaFile):
                    files.append(media)
            if not files:
                continue
            event = Event(event_id=i + 1, name=item.text(0), files=files)
            for media in files:
                media.event_id = event.event_id
            events.append(event)
        return events

    # -- drag & drop ----------------------------------------------------- #
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drops, then prune any event that became empty."""
        super().dropEvent(event)
        self._prune_empty_events()

    def _prune_empty_events(self) -> None:
        for i in reversed(range(self.topLevelItemCount())):
            item = self.topLevelItem(i)
            if item is not None and item.childCount() == 0:
                self.takeTopLevelItem(i)
