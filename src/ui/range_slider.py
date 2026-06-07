"""Custom dual-point range slider widget for audio trimming."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import QWidget

from src.utils.time_format import format_seconds


class RangeSlider(QWidget):
    """A horizontal slider with two draggable handles for selecting a range.
    
    Shows time labels at start (0:00) and end (duration).
    """
    
    range_changed = Signal(float, float)  # start_seconds, end_seconds
    
    def __init__(
        self,
        duration_seconds: float = 0.0,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._duration = max(0.1, duration_seconds)
        self._start_ratio = 0.0  # 0.0 to 1.0
        self._end_ratio = 1.0    # 0.0 to 1.0
        
        # Handle drag state
        self._dragging: Optional[str] = None  # "start", "end", or None
        
        # Dimensions
        self._handle_radius = 8
        self._track_height = 6
        self._margin = 20  # margin for handles
        
        self.setMinimumHeight(40)
        self.setMouseTracking(True)
    
    def set_duration(self, duration: float) -> None:
        """Update the total duration.
        
        Args:
            duration: Duration in seconds.
        """
        self._duration = max(0.1, duration)
        self.update()
    
    def set_range(self, start_seconds: float, end_seconds: float) -> None:
        """Set the trim range programmatically.
        
        Args:
            start_seconds: Start position in seconds.
            end_seconds: End position in seconds.
        """
        if self._duration <= 0:
            return
        self._start_ratio = max(0.0, min(1.0, start_seconds / self._duration))
        self._end_ratio = max(0.0, min(1.0, end_seconds / self._duration))
        if self._start_ratio >= self._end_ratio:
            self._end_ratio = min(1.0, self._start_ratio + 0.01)
        self.update()
    
    @property
    def start_seconds(self) -> float:
        """Get start trim position in seconds."""
        return self._start_ratio * self._duration
    
    @property
    def end_seconds(self) -> float:
        """Get end trim position in seconds."""
        return self._end_ratio * self._duration
    
    def _track_rect(self) -> QRectF:
        """Get the bounding rect for the slider track."""
        width = self.width() - 2 * self._margin
        y = self.height() / 2 - self._track_height / 2
        return QRectF(self._margin, y, width, self._track_height)
    
    def _handle_pos(self, ratio: float) -> QPointF:
        """Get the center position of a handle at the given ratio."""
        track = self._track_rect()
        x = track.x() + ratio * track.width()
        y = track.y() + track.height() / 2
        return QPointF(x, y)
    
    def _ratio_from_pos(self, x: float) -> float:
        """Convert an x-coordinate to a ratio value."""
        track = self._track_rect()
        if track.width() <= 0:
            return 0.0
        ratio = (x - track.x()) / track.width()
        return max(0.0, min(1.0, ratio))
    
    def _handle_hit(self, pos: QPointF, ratio: float) -> bool:
        """Check if a position is within the hit area of a handle."""
        handle_pos = self._handle_pos(ratio)
        dx = pos.x() - handle_pos.x()
        dy = pos.y() - handle_pos.y()
        return (dx * dx + dy * dy) <= (self._handle_radius * 4 * self._handle_radius * 4)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        pos = event.position()
        
        # Check if hitting start handle
        if self._handle_hit(pos, self._start_ratio):
            self._dragging = "start"
        # Check if hitting end handle
        elif self._handle_hit(pos, self._end_ratio):
            self._dragging = "end"
        else:
            # Click on track — move nearest handle
            track = self._track_rect()
            if track.contains(pos):
                click_ratio = self._ratio_from_pos(pos.x())
                dist_start = abs(click_ratio - self._start_ratio)
                dist_end = abs(click_ratio - self._end_ratio)
                if dist_start <= dist_end:
                    self._dragging = "start"
                    self._start_ratio = click_ratio
                else:
                    self._dragging = "end"
                    self._end_ratio = click_ratio
                self.range_changed.emit(self.start_seconds, self.end_seconds)
                self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is None:
            # Update cursor
            pos = event.position()
            if (self._handle_hit(pos, self._start_ratio) or
                self._handle_hit(pos, self._end_ratio)):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        pos = event.position()
        ratio = self._ratio_from_pos(pos.x())
        
        if self._dragging == "start":
            self._start_ratio = max(0.0, min(self._end_ratio - 0.01, ratio))
        elif self._dragging == "end":
            self._end_ratio = min(1.0, max(self._start_ratio + 0.01, ratio))
        
        self.range_changed.emit(self.start_seconds, self.end_seconds)
        self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging is not None:
            self._dragging = None
            self.range_changed.emit(self.start_seconds, self.end_seconds)
            self.update()
    
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        track = self._track_rect()
        start_pos = self._handle_pos(self._start_ratio)
        end_pos = self._handle_pos(self._end_ratio)
        
        # Colors
        bg_color = QColor(60, 60, 60)
        range_color = QColor(0, 150, 255)
        handle_color = QColor(200, 200, 200)
        handle_border = QColor(150, 150, 150)
        text_color = QColor(200, 200, 200)
        
        # Draw background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(track, 3, 3)
        
        # Draw selected range
        range_rect = QRectF(
            start_pos.x(), track.y(),
            end_pos.x() - start_pos.x(), track.height()
        )
        painter.setBrush(QBrush(range_color))
        painter.drawRoundedRect(range_rect, 3, 3)
        
        # Draw handles
        painter.setPen(QPen(handle_border, 1.5))
        painter.setBrush(QBrush(handle_color))
        
        # Start handle
        painter.drawEllipse(start_pos, self._handle_radius, self._handle_radius)
        # End handle
        painter.drawEllipse(end_pos, self._handle_radius, self._handle_radius)
        
        # Draw time labels
        painter.setPen(text_color)
        font = QFont("monospace", 9)
        painter.setFont(font)
        
        painter.drawText(
            int(self._margin), self.height() - 5,
            format_seconds(self.start_seconds)
        )
        
        # End label aligned to right
        end_label = format_seconds(self.end_seconds)
        end_label_width = painter.fontMetrics().horizontalAdvance(end_label)
        painter.drawText(
            int(self.width() - self._margin - end_label_width),
            self.height() - 5,
            end_label
        )
        
        # Duration label at center
        duration_label = format_seconds(self._duration)
        dur_width = painter.fontMetrics().horizontalAdvance(duration_label)
        painter.drawText(
            int(self.width() / 2 - dur_width / 2),
            self.height() - 5,
            duration_label
        )
