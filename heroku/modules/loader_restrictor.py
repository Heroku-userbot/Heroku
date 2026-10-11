# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# scope: no_ml

import asyncio
import logging

from dataclasses import dataclass

from herokutl.extensions import html
from herokutl.tl.types import (
    InputMediaPoll,
    Poll,
    PollAnswer,
    TextWithEntities,
    UpdateMessagePollVote,
)
from herokutl.tl.custom import Message

from .. import loader
from ..inline.types import BotInlineCall, BotInlineMessage

logger = logging.getLogger(__name__)

ANS_COUNT = 4


@dataclass()
class PollStep:
    key: str
    answer_index: int

    @property
    def answer_keys(self):
        return [f"{self.key}_ans{i + 1}" for i in range(ANS_COUNT)]

    @property
    def hint(self):
        return f"{self.key}_hint"

    def is_correct(self, index: int):
        return self.answer_index == index


@dataclass()
class PollStatus:
    poll_id: int
    message_ids: list[int]
    answers: list[bool]
    step: int


QUESTIONS = [
    PollStep("q1", 3),
    PollStep("q2", 1),
    PollStep("q3", 2),
    PollStep("q4", 3),
]


@loader.tds
class LoaderRestrictor(loader.Module):
    strings = {"name": "LoaderRestrictor"}

    async def client_ready(self):
        self.poll: PollStatus | None = None

    async def inline_ready(self):
        if self.get("passed", False):
            return

        try:
            await self.inline.bot.send_message(
                self.client.tg_id,
                self.strings["unlock_prompt"],
                reply_markup=self.inline.generate_markup(
                    [
                        [
                            {
                                "text": self.strings["unlock_prompt_btn"],
                                "callback": self._unlock_prompt_callback,
                            }
                        ]
                    ]
                ),
            )
        except Exception:
            logger.debug("Can't send unlock prompt", exc_info=True)

    async def _unlock_prompt_callback(self, call: BotInlineCall):
        await call.delete()
        await self._start_quiz()

    def _build_poll(self, poll_step: PollStep) -> InputMediaPoll:
        poll = Poll(
            id=0,
            question=TextWithEntities(*html.parse(self.strings[poll_step.key])),
            answers=[
                PollAnswer(
                    text=TextWithEntities(*html.parse(self.strings[ans])),
                    option=str(i),
                )
                for i, ans in enumerate(poll_step.answer_keys)
            ],
            hash=0,
            quiz=True,
            public_voters=True,
            revoting_disabled=True,
            close_period=60,
        )
        solution, solution_entities = html.parse(self.strings[poll_step.hint])
        return InputMediaPoll(
            poll=poll,
            correct_answers=[poll_step.answer_index],
            solution=solution,
            solution_entities=solution_entities,
        )

    @loader.need_update("poll_answer")
    async def poll_handler(self, update: UpdateMessagePollVote):
        if self.get("passed", False):
            return

        if not self.poll or not update.poll_id == self.poll.poll_id:
            return

        correct = update.positions[0] == QUESTIONS[self.poll.step].answer_index
        self.poll.answers.append(correct)

        if not correct:
            return await self._abort_quiz("failed")

        await self._next_step_quiz()

    async def _watch_timeout(self, poll_id: int):
        await asyncio.sleep(60)
        if self.poll and self.poll.poll_id == poll_id:
            await self._abort_quiz("timeout")

    async def _start_quiz(self):
        if self.get("passed", False):
            await self.inline.bot.send_message(
                self.client.tg_id,
                self.strings["already_passed"],
            )
            return

        if self.poll:
            await self.inline.bot.delete_message(
                self.client.tg_id, self.poll.message_ids
            )

        step = QUESTIONS[0]
        poll_m: Message = await self.inline.bot.send_file(
            self.client.tg_id,
            file=self._build_poll(step),
        )

        self.poll = PollStatus(
            poll_id=poll_m.media.poll.id,
            message_ids=[poll_m.id],
            answers=[],
            step=0,
        )
        asyncio.create_task(self._watch_timeout(self.poll.poll_id))

    async def _next_step_quiz(self):
        if self.poll.step == len(QUESTIONS) - 1:
            return await self._end_quiz()

        self.poll.step += 1
        question = QUESTIONS[self.poll.step]

        poll_m: Message = await self.inline.bot.send_file(
            self.client.tg_id,
            file=self._build_poll(question),
        )
        self.poll.message_ids.append(poll_m.id)
        self.poll.poll_id = poll_m.media.poll.id
        asyncio.create_task(self._watch_timeout(self.poll.poll_id))

    async def _end_quiz(self):
        message_ids = self.poll.message_ids
        self.poll = None
        self.set("passed", True)

        await self.inline.bot.delete_message(self.client.tg_id, message_ids)
        await self.inline.bot.send_message(
            self.client.tg_id,
            self.strings["unlocked"],
        )

    async def _abort_quiz(self, message_key: str):
        self.poll = None
        await self.inline.bot.send_message(
            self.client.tg_id,
            self.strings[message_key],
        )

    async def bot_watcher(self, message: BotInlineMessage):
        if (
            message.text != "/start lm_verify"
            or message.sender_id != self.client.tg_id
        ):
            return

        await message.delete()

        await self._start_quiz()

