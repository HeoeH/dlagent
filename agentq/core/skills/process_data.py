import json
import os
from typing import Callable, List, Optional, Tuple, Type

import instructor
import instructor.patch
import litellm
import openai
from instructor import Mode
from langsmith import traceable
from pydantic import BaseModel

from agentq.core.models.models import AgentQActorInput
from agentq.utils.function_utils import get_function_schema
from agentq.utils.logger import logger
from agentq.core.prompts.prompts import LLM_PROMPTS
from agentq.core.models.models import TaskWithActions


def process_data(input_data: AgentQActorInput, response: TaskWithActions) -> List[dict]:
    messages = []
    user_message = {
        "from": "user",
        "value": f"{input_data.model_dump_json(exclude={'current_base64_img'})}\n<image>"
    }
    assistant_message = {
        "from": "assistant",
        "value": response.model_dump_json()
    }
    messages.append(user_message)
    messages.append(assistant_message)
    return messages




