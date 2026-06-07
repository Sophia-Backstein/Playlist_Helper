"""Command pattern implementation for undo/redo functionality."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional


class Command(ABC):
    """Abstract base for all undoable commands."""
    
    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        ...
    
    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        ...
    
    @abstractmethod
    def redo(self) -> None:
        """Redo the command (re-execute after undo)."""
        ...


class CallbackCommand(Command):
    """Command that wraps callable functions for execute/undo/redo."""
    
    def __init__(
        self,
        execute_fn: Callable[[], None],
        undo_fn: Callable[[], None],
        description: str = "",
    ):
        self._execute_fn = execute_fn
        self._undo_fn = undo_fn
        self.description = description
    
    def execute(self) -> None:
        self._execute_fn()
    
    def undo(self) -> None:
        self._undo_fn()
    
    def redo(self) -> None:
        self.execute()


class UndoableAction:
    """Tracks a state change with before/after snapshots."""
    
    def __init__(
        self,
        apply_change: Callable[[], None],
        revert_change: Callable[[], None],
        description: str = "",
    ):
        self.apply_change = apply_change
        self.revert_change = revert_change
        self.description = description


class CommandHistory:
    """Manages a stack of commands for undo/redo.
    
    Provides undo and redo capabilities with bounded stack size.
    """
    
    def __init__(self, max_size: int = 100):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_size = max_size
        self._state_change_callbacks: List[Callable[[], None]] = []
    
    def push(self, command: Command) -> None:
        """Execute a command and push it onto the undo stack.
        
        Args:
            command: The command to execute and store.
        """
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._notify()
    
    def push_action(self, action: UndoableAction) -> None:
        """Convenience: wrap an UndoableAction as a Command and push.
        
        Args:
            action: The action to execute and track.
        """
        command = CallbackCommand(
            execute_fn=action.apply_change,
            undo_fn=action.revert_change,
            description=action.description,
        )
        self.push(command)
    
    def undo(self) -> bool:
        """Undo the last command.
        
        Returns:
            True if a command was undone, False if nothing to undo.
        """
        if not self._undo_stack:
            return False
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        self._notify()
        return True
    
    def redo(self) -> bool:
        """Redo the last undone command.
        
        Returns:
            True if a command was redone, False if nothing to redo.
        """
        if not self._redo_stack:
            return False
        command = self._redo_stack.pop()
        command.redo()
        self._undo_stack.append(command)
        self._notify()
        return True
    
    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def clear(self) -> None:
        """Clear all command stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify()
    
    def on_state_change(self, callback: Callable[[], None]) -> None:
        """Register a callback for when undo/redo state changes."""
        self._state_change_callbacks.append(callback)
    
    def _notify(self) -> None:
        for cb in self._state_change_callbacks:
            cb()
