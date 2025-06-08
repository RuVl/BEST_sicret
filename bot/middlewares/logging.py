import time
import traceback
import types
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.dispatcher.middlewares.user_context import EVENT_FROM_USER_KEY
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, User
from structlog import get_logger
from structlog.typing import FilteringBoundLogger


class LoggingMw(BaseMiddleware):
	"""Middleware for structured logging of handler calls and state changes."""

	def __init__(self, middleware_key: str = 'log', *, patch_fsm: bool = True):
		self.logger: FilteringBoundLogger = get_logger()
		self.middleware_key = middleware_key
		self.patch_fsm = patch_fsm

	@staticmethod
	def get_user_context(user: Optional[User]) -> dict:
		"""Creates a context dictionary with user information for logging."""
		context = {}
		if user:
			context.update({
				"user_id": user.id,
				"username": user.username,
				"telegram_name": f"{user.first_name} {user.last_name or ''}".strip(),
			})
		return context

	def patch_fsm_methods(self, fsm: FSMContext, log: FilteringBoundLogger):
		"""Patch FSM methods to add logging capabilities."""
		if not self.patch_fsm:
			return

		original_set_state = fsm.set_state

		async def set_state_with_logging(_, state):
			state_value = "cleared" if state is None else str(state.state)
			await log.adebug("state-changed", state=state_value)
			return await original_set_state(state)

		fsm.set_state = types.MethodType(set_state_with_logging, fsm)

	async def __call__(
			self,
			handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
			event: TelegramObject,
			data: Dict[str, Any],
	) -> Any:
		telegram_user = data.get(EVENT_FROM_USER_KEY)
		user_context = self.get_user_context(telegram_user)

		# Create child logger with user context
		log = self.logger.bind(**user_context)
		data[self.middleware_key] = log

		# Get handler name for logging
		handler_obj = data.get("handler")
		handler_name = (
			getattr(handler_obj.callback, "__name__", str(handler_obj.callback))
			if handler_obj and hasattr(handler_obj, "callback") else
			getattr(handler, "__name__", str(handler))
		)

		# Log handler call
		await log.adebug("handler-called", handler=handler_name)

		# Add logging to FSM state changes
		state: FSMContext = data.get("state")
		if state and self.patch_fsm:
			self.patch_fsm_methods(state, log)

		try:
			# Measure execution time
			start = time.perf_counter()
			result = await handler(event, data)
			end = time.perf_counter()

			execution_time = round(end - start, 3)

			# Log successful completion
			await log.adebug("handler-completed", handler=handler_name, execution_time=execution_time)
			return result

		except Exception as e:
			# Get full exception traceback for error logs
			tb = traceback.format_exc()

			# Log error with detailed context
			await log.aerror(
				"handler-error",
				handler=handler_name,
				error_type=type(e).__name__,
				error=str(e),
				traceback=tb
			)
			# Re-raise to let error handlers deal with it
			raise
