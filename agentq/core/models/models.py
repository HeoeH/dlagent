from enum import Enum, IntEnum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel
from pydantic.fields import Field


# Global
class State(str, Enum):
    PLAN = "plan"
    BROWSE = "browse"
    COMPLETED = "completed"
    AGENTQ_BASE = "agentq_base"
    AGENTQ_ACTOR = "agentq_actor"
    AGENTQ_CRITIC = "agentq_critic"


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    GOTO_URL = "GOTO_URL"
    ENTER_TEXT_AND_CLICK = "ENTER_TEXT_AND_CLICK"
    SOLVE_CAPTCHA = "SOLVE_CAPTCHA"
    SCROLL= "SCROLL"
    HOVER = "HOVER"
    NEW_TAB= "NEW_TAB"
    GO_BACK= "GO_BACK"
    GO_FORWARD= "GO_FORWARD"
    PAGE_CLOSE= "PAGE_CLOSE"
    KEY_PRESS = "KEY_PRESS"
    STOP= "STOP"
    # GET_DOM_TEXT_CONTENT = "GET_DOM_TEXT_CONTENT"
    # GET_DOM_INPUT_FILEDS = "GET_DOM_INPUT_FILEDS"
    # GET_DOM_ALL_CONTENTS = "GET_DOM_ALL_CONTENTS"
    # GET_CURRENT_URL = "GET_CURRENT_URL"


class ClickAction(BaseModel):
    type: Literal[ActionType.CLICK] = Field(
        description="""Executes a click action on the element matching the given mmid attribute value. MMID is always a number. Returns Success if click was successful or appropriate error message if the element could not be clicked."""
    )
    mmid: int = Field(
        description="The mmid number of the element that needs to be clicked e.g. 114. mmid will always be a number"
    )
    wait_before_execution: Optional[float] = Field(
        description="Optional wait time in seconds before executing the click event logic"
    )

class HoverAction(BaseModel):
    type: Literal[ActionType.HOVER] = Field(
        description="""Executes a hover action on the element matching the given mmid attribute value. MMID is always a number. Returns Success if hover was successful or appropriate error message if the element could not be hovered."""
    )
    mmid: int = Field(
        description="The mmid number of the element that needs to be clicked e.g. 114. mmid will always be a number"
    )

class NewTabAction(BaseModel):
    type: Literal[ActionType.NEW_TAB] = Field(
        description=""" Open a new tab on the current page. Returns Success if new tab was opened or appropriate error message if the tab could not be opened."""
    )

class PressKeyAction(BaseModel):
    type: Literal[ActionType.KEY_PRESS] = Field(
        description=""" Press a combination of keys described by action_str on the keyboard.Return Success if keys were successfully pressed or appropriate error message if the keys could not be pressed."""
    )
    action_str: str = Field(
        "The combination of keys to press on the keyboard. e.g. 'Control+Shift+T' to open a closed tab."
    )
class GoBackAction(BaseModel):
    type: Literal[ActionType.GO_BACK] = Field(
        description=""" Go back to the previous page.Returns Success if page was successfully navigated to the previous page or appropriate error message if the page could not be navigated."""
    )

class STOPAction(BaseModel):
    type: Literal[ActionType.STOP] = Field(
        description=""" Stop the current browser page.Returns Success if page was successfully stopped or appropriate error message if the page could not be stopped."""
    )
    answer: str = Field(
        description="The answer to the instruction that the agent finally gets."
    )

class GoForwardAction(BaseModel):
    type: Literal[ActionType.GO_FORWARD] = Field(
        description=""" Navigates forward to the next page in the browser's history. If there is no next page in the history, it has no effect. Simply put, it functions like the forward button in a browser. Returns Success if page was successfully navigated to the next page or appropriate error message if the page could not be navigated."""
    )

class PageCloseAction(BaseModel):
    type: Literal[ActionType.PAGE_CLOSE] = Field(
        description=""" Close the current browser page.Returns Success if page was successfully closed or appropriate error message if the page could not be closed."""
    )


class TypeAction(BaseModel):
    type: Literal[ActionType.TYPE] = Field(
        description="""Single enter given text in the DOM element matching the given mmid attribute value. This will only enter the text and not press enter or anything else.
   Returns Success if text entry was successful or appropriate error message if text could not be entered."""
    )
    mmid: int = Field(
        description="The mmid number of the element that needs to be clicked e.g. 114. mmid will always be a number"
    )
    content: str = Field(
        description="The text to enter in the element identified by the query_selector."
    )


class GotoAction(BaseModel):
    type: Literal[ActionType.GOTO_URL] = Field(
        description="Opens a specified URL in the web browser instance. Returns url of the new page if successful or appropriate error message if the page could not be opened."
    )
    website: str = Field(
        description="The URL to navigate to. Value must include the protocol (http:// or https://)."
    )
    timeout: Optional[float] = Field(
        description="Additional wait time in seconds after initial load."
    )

class ScrollAction(BaseModel):
    type: Literal[ActionType.SCROLL] = Field(
        description="""Scroll the page up or down to see more information."""
    )
    direction: str = Field(
        description="The direction of scroll action."
    )



class EnterTextAndClickAction(BaseModel):
    type: Literal[ActionType.ENTER_TEXT_AND_CLICK] = Field(
        description="""Enters text into a specified element and clicks another element, both identified by their mmid. Ideal for seamless actions like submitting search queries, this integrated approach ensures superior performance over separate text entry and click commands. Successfully completes when both actions are executed without errors, returning True; otherwise, it provides False or an explanatory message of any failure encountered."""
    )
    text_element_mmid: int = Field(
        description="The mmid number of the element where the text will be entered"
    )
    text_to_enter: str = Field(
        description="The text that will be entered into the element specified by text_element_mmid"
    )
    click_element_mmid: int = Field(
        description="The mmid number of the element that will be clicked after text entry."
    )
    wait_before_click_execution: Optional[float] = Field(
        description="Optional wait time in seconds before executing the click event logic"
    )


class SolveCaptcha(BaseModel):
    type: Literal[ActionType.SOLVE_CAPTCHA] = Field(
        description="""Solve captcha, enters the solve captcha into a specified element and clicks another element, both identified by their mmid. Ideal for captcha solving ,entering captcha and clicking submit.Successfully completes when all three actions are executed without errors, returning True; otherwise, it provides False or an explanatory message of any failure encountered."""
    )
    text_element_mmid: int = Field(
        description="The mmid number of the element where the captcha will be entered"
    )

    click_element_mmid: int = Field(
        description="The mmid number of the element that will be clicked after the catcha entry to submit"
    )

    wait_before_click_execution: Optional[float] = Field(
        description="Optional wait time in seconds before executing the click event logic"
    )


class Score(IntEnum):
    FAIL = 0
    PASS = 1


# class GetDomTextAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_TEXT_CONTENT]


# class GetDomInputsAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_INPUT_FILEDS]


# class GetDomAllAction(BaseModel):
#     type: Literal[ActionType.GET_DOM_ALL_CONTENTS]


# class GetCurrentUrlAction(BaseModel):
#     type: Literal[ActionType.GET_CURRENT_URL]


Action = Union[
    ClickAction,
    TypeAction,
    GotoAction,
    EnterTextAndClickAction,
    SolveCaptcha,
    ScrollAction,
    HoverAction,
    NewTabAction,
    GoBackAction,
    GoForwardAction,
    PageCloseAction,
    PressKeyAction,
    STOPAction,
    # GetDomTextAction,
    # GetDomInputsAction,
    # GetDomAllAction,
    # GetCurrentUrlAction,
]


class Task(BaseModel):
    id: int
    description: str
    url: Optional[str]
    result: Optional[str]


class TaskWithActions(BaseModel):
    id: int
    description: str
    actions_to_be_performed: Optional[List[Action]]
    result: Optional[str]


class Memory(BaseModel):
    objective: str
    current_state: State
    plan: Optional[Union[List[Task], List[TaskWithActions]]]
    thought: str
    completed_tasks: Optional[Union[List[Task], List[TaskWithActions]]]
    current_task: Optional[Union[Task, TaskWithActions]]
    final_response: Optional[str]
    current_tasks_for_eval: Optional[List[TaskWithActions]]
    sorted_tasks: Optional[List[TaskWithActions]]

    class Config:
        use_enum_values = True


# Planner
class PlannerInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[Task]]
    task_for_review: Optional[Task]


class PlannerOutput(BaseModel):
    plan: Optional[List[Task]]
    thought: str
    next_task: Optional[Task]
    is_complete: bool
    final_response: Optional[str]


# Executor
class BrowserNavInput(BaseModel):
    task: Task


class BrowserNavOutput(BaseModel):
    completed_task: Task


# AgentQ
class AgentQBaseInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[Task]]
    current_base64_img: str
    current_web_text: str


class AgentQBaseOutput(BaseModel):
    thought: str
    plan: List[Task]
    next_task: Optional[Task]
    next_task_actions: Optional[List[Action]]
    is_complete: bool
    final_response: Optional[str]


# Actor
class AgentQActorInput(BaseModel):
    objective: str
    completed_tasks: Optional[List[TaskWithActions]]
    current_web_text: str
    current_base64_img: str


class AgentQActorOutput(BaseModel):
    thought: str
    proposed_tasks: Optional[List[TaskWithActions]]
    is_complete: bool
    final_response: Optional[str]


# Critic


class AgentQCriticInput(BaseModel):
    history_completed_tasks: Optional[List[TaskWithActions]]
    current_task: Optional[TaskWithActions]
    current_base64_img: str


# class AgentQCriticInput(BaseModel):
#     objective: str
#     completed_tasks: Optional[List[TaskWithActions]]
#     tasks_for_eval: List[TaskWithActions]
#     current_base64_img: str
#     current_web_text:str

# class AgentQCriticOutput(BaseModel):
#     thought: str
#     top_task: TaskWithActions


class AgentQCriticOutput(BaseModel):
    thought: str
    description: str
    done_objective: str


# # Vision
# class VisionInput(BaseModel):
#     completed_tasks: Optional[List[TaskWithActions]]
#     current_base64_img: str


# class VisionOutput(BaseModel):
#     thought: str
#     description:str
#     predict_objective:str


# Vision
class VisionInput(BaseModel):
    origin_instruction: str
    done_description: str


class VisionOutput(BaseModel):
    thought: str
    matching_score: float

class FailFilterInput(BaseModel):
    completed_tasks: Optional[List[TaskWithActions]]
    objective: str
    current_base64_img: str
    done_description: str

class FailFilterOutput(BaseModel):
    thought: str
    repeatability: float
    ineffectiveness: float
    exploratory: float
    logicality: float
    is_useless: bool


class EvalAgentInput(BaseModel):
    objective: str
    agent_output: str
    current_page_url: str
    current_page_dom: str


class EvalAgentOutput(BaseModel):
    score: Score


class CaptchaAgentInput(BaseModel):
    objective: str


class CaptchaAgentOutput(BaseModel):
    captcha: str
    success: bool


# Monte-Carlo
class BrowserState(BaseModel):
    web_text: str
    base64_img: str
    img_path:str
    current_url: str
    objective: str
    done_objective: str
    completed_tasks: Optional[List[TaskWithActions]]
    done_description: str


class BrowserAction(BaseModel):
    task_with_action: TaskWithActions
    rank: float = Field(description="The rank of this action, higher is better")


class DPOState(BaseModel):
    objective: str
    dom: str


class DPOAction(BaseModel):
    description: str
    action: Action


class DPOPair(BaseModel):
    state: DPOState
    winning_action: DPOAction
    losing_action: DPOAction
