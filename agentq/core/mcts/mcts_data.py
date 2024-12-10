import asyncio
import json
import sys
from typing import List, Tuple
import re
import numpy as np
import argparse
import os
import json
import asyncio
from langsmith import traceable
from playwright.async_api import Page
from agentq.core.prompts.prompts import LLM_PROMPTS
from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
from agentq.core.agent.agentq_filter import FailFilter
from agentq.core.agent.base import BaseAgent
from agentq.core.agent.vision_agent import VisionAgent
from agentq.core.mcts.core.base import Reasoner, SearchConfig, WorldModel
from agentq.core.mcts.core.mcts import MCTS, MCTSResult
from agentq.core.models.models import (
    ActionType,
    AgentQActorInput,
    AgentQActorOutput,
    AgentQCriticInput,
    AgentQCriticOutput,
    BrowserAction,
    BrowserState,
    DPOAction,
    DPOPair,
    DPOState,
    TaskWithActions,
    VisionInput,
    VisionOutput,
    FailFilterInput,
    FailFilterOutput,
)
import os
import sys
import logging
import glob
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.skills.process_data import process_data
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.web_driver.playwright import PlaywrightManager
# 设置要使用的 GPU 卡号，例如使用 GPU 卡号 0
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


# ANSI color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

SPECIAL_KEY_MAPPINGS = {
    "backquote": "Backquote",
    "minus": "Minus",
    "equal": "Equal",
    "backslash": "Backslash",
    "backspace": "Backspace",
    "meta": "Meta",
    "tab": "Tab",
    "delete": "Delete",
    "escape": "Escape",
    "arrowdown": "ArrowDown",
    "end": "End",
    "enter": "Enter",
    "home": "Home",
    "insert": "Insert",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
}

@traceable(run_type="chain", name="mcts")
class BrowserWorldModel(WorldModel[BrowserState, BrowserAction, str]):
    def __init__(self, objective: str, vision: BaseAgent, critic: BaseAgent,task_id:str) -> None:
        super().__init__()
        self.objective = objective
        self.vision = vision
        self.critic = critic
        self.task_id = task_id
        print(
            f"{BLUE}[DEBUG] BrowserWorldModel initialized with objective: {self.objective}{RESET}"
        )

    async def init_state(self) -> BrowserState:
        # go to home page
        print(f"{GREEN}[DEBUG] GOING TO INIT STATE HOMEPAGE{RESET}")
        playwright_manager = PlaywrightManager()
        await playwright_manager.go_to_homepage()
        page: Page = await playwright_manager.get_current_page()

        # if eval_mode:
        #     await page.set_extra_http_headers({"User-Agent": "AgentQ-Bot"})
        # rects, web_eles, web_eles_text = await get_web_element_rect(page, fix_color=True)
        # print(f"{GREEN}[DEBUG] Initial rects(SoM) created")

        screenshot,img_path = await get_screenshot(page,task_id)

        # initialzie dom and url
        initial_dom = await self.get_current_dom()
        initial_url = await self.get_current_url()
        print(f"{GREEN}[DEBUG] Initial state created - URL: {initial_url}{RESET}")

        return BrowserState(
            web_text=initial_dom,
            base64_img=screenshot,
            img_path=img_path,
            current_url=initial_url,
            objective=self.objective,
            done_objective=self.objective,
            completed_tasks=[],
            done_description="",
        )

    async def step(
        self, state: BrowserState, browser_action: BrowserAction
    ) -> Tuple[BrowserState, dict]:
        print(f"{YELLOW}[DEBUG] Executing step with action: {browser_action}{RESET}")
        
        try:
            new_dom, new_url, new_base64_img,new_img_path = await self.execute_browser_action(
            browser_action
            )
            current_task = browser_action.task_with_action
            new_completed_tasks = state.completed_tasks + [current_task]
            new_state = BrowserState(
            base64_img=new_base64_img,
            img_path=new_img_path,
            web_text=new_dom,
            current_url=new_url,
            objective=state.objective,
            done_objective=state.done_objective,
            completed_tasks=new_completed_tasks,
            done_description=state.done_description
            )
            print(f"{GREEN}[DEBUG] New state after step - URL: {new_url}{RESET}")
            return new_state, {}
        except Exception as e:
            raise Exception("Error: Unable to execute action")

    async def is_terminal(self, state: BrowserState) -> bool:
        print(f"completed_task_world:{state.completed_tasks}")
        terminal = await is_terminal(state, self.vision, self.critic)
        print(f"{CYAN}[DEBUG] is_terminal: {terminal}{RESET}")
        return terminal

    async def execute_browser_action(
        self, browser_action: BrowserAction
    ) -> Tuple[str, str, str]:
        browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
        await browser_manager.get_browser_context()
        page = await browser_manager.get_current_page()

        async def retry_action(action_func, retries=3, delay=1):
            for attempt in range(retries):
                try:
                    await action_func()
                    return True
                except Exception as e:
                    if attempt < retries - 1:
                        print(f"{RED}[DEBUG] Action failed with error: {e}. Retrying...{RESET}")
                        await asyncio.sleep(delay)
                    else:
                        return False
                        


                            
        for action in browser_action.task_with_action.actions_to_be_performed:
            print(f"{YELLOW}[DEBUG] Executing browser action: {action.type}{RESET}")
            try:
                if action.type == ActionType.GOTO_URL:
                    async def goto_url_action():
                        await openurl(url=action.website, timeout=action.timeout or 1)
                    if await retry_action(goto_url_action):
                        print(f"{CYAN}[DEBUG] Went to url{RESET}")
                    else :
                        raise Exception("Failed to open url")
                elif action.type == ActionType.TYPE:
                    entry = EnterTextEntry(
                        query_selector=f"[mmid='{action.mmid}']",
                        text=action.content,
                    )
                    async def type_action():
                        await page.wait_for_selector(f"[mmid='{action.mmid}']", state='visible', timeout=60000)
                        await entertext(entry)
                    if await retry_action(type_action):
                        print(f"{CYAN}[DEBUG] Typed text into element{RESET}")
                    else :
                        raise Exception("Failed to type text")
                elif action.type == ActionType.CLICK:
                    async def click_action():
                        await page.wait_for_selector(f"[mmid='{action.mmid}']", state='visible', timeout=60000)
                        await click(
                            selector=f"[mmid='{action.mmid}']",
                            wait_before_execution=action.wait_before_execution or 2,
                        )
                    if await retry_action(click_action):
                        print(f"{CYAN}[DEBUG] Clicked element{RESET}")
                    else :
                        raise Exception("Failed to click element")
                elif action.type == ActionType.ENTER_TEXT_AND_CLICK:
                    async def enter_text_and_click_action():
                        result = await enter_text_and_click(
                            text_selector=f"[mmid='{action.text_element_mmid}']",
                            text_to_enter=action.text_to_enter,
                            click_selector=f"[mmid='{action.click_element_mmid}']",
                            wait_before_click_execution=2,
                        )
                        if not result:
                            raise Exception(f"Failed to enter text '{action.text_to_enter}' into element with selector '[mmid='{action.text_element_mmid}']'. Check that the selector is valid.")
                    if await retry_action(enter_text_and_click_action):
                        print(f"{CYAN}[DEBUG] Entered text and clicked element{RESET}")
                    else:
                        raise Exception("Failed to enter text and click element")
                elif action.type == ActionType.HOVER:
                    async def hover_action():
                        await page.wait_for_selector(f"[mmid='{action.mmid}']", state='visible', timeout=60000)
                        await page.hover(selector=f"[mmid='{action.mmid}']")
                    if await retry_action(hover_action):
                        print(f"{CYAN}[DEBUG] Hovered over element{RESET}")
                    else:
                        raise Exception("Failed to hover over element")
                elif action.type == ActionType.SCROLL:
                    direction = "up" if "up" in action.direction else "down"
                    async def scroll_action():
                        if direction == "up":
                            await page.evaluate(
                                "(document.scrollingElement || document.body).scrollTop = (document.scrollingElement || document.body).scrollTop - window.innerHeight;"
                            )
                        elif direction == "down":
                            await page.evaluate(
                                "(document.scrollingElement || document.body).scrollTop = (document.scrollingElement || document.body).scrollTop + window.innerHeight;"
                            )
                    if await retry_action(scroll_action):
                        print(f"{CYAN}[DEBUG] Scrolled {direction}{RESET}")
                    else:
                        raise Exception("Failed to scroll")
                elif action.type == ActionType.KEY_PRESS:
                    keys = action.action_str
                    match = re.search(r"press ?\[(.+)\]", keys)
                    if not match:
                        raise ValueError(f"Invalid press action {keys}")
                    key_comb = match.group(1)
                    keys = key_comb.split("+")
                    mapped_keys = []
                    for key in keys:
                        mapped_key = SPECIAL_KEY_MAPPINGS.get(key.lower(), key)
                        mapped_keys.append(mapped_key)
                    mapped_keys = "+".join(mapped_keys)
                    async def key_press_action():
                        await page.keyboard.press(mapped_keys)
                    if await retry_action(key_press_action):
                        print(f"{CYAN}[DEBUG] Pressed keys: {mapped_keys}{RESET}")
                    else:
                        raise Exception("Failed to press keys")
                elif action.type == ActionType.NEW_TAB:
                    async def new_tab_action():
                        browser_ctx = await browser_manager.get_browser_context()
                        page = await browser_ctx.new_page()
                        await page.goto("https://www.google.com")
                    if await retry_action(new_tab_action):
                        print(f"{CYAN}[DEBUG] Opened new tab{RESET}")
                    else:
                        raise Exception("Failed to open new tab")
                elif action.type == ActionType.GO_BACK:
                    async def go_back_action():
                        await page.go_back()
                    if await retry_action(go_back_action):
                        print(f"{CYAN}[DEBUG] Navigated back{RESET}")
                    else:
                        raise Exception("Failed to navigate back")
                elif action.type == ActionType.GO_FORWARD:
                    async def go_forward_action():
                        await page.go_forward()
                    if await retry_action(go_forward_action):
                        print(f"{CYAN}[DEBUG] Navigated forward{RESET}")
                    else:    
                        raise Exception("Failed to navigate forward")
                elif action.type == ActionType.PAGE_CLOSE:
                    async def page_close_action():
                        await page.close()
                        pages = await page.context.pages()
                        if len(pages) == 0:
                            new_page = await page.context.new_page()
                            await new_page.goto("https://www.google.com")
                    if await retry_action(page_close_action):
                        print(f"{CYAN}[DEBUG] Closed page{RESET}")
                    else:             
                        raise Exception("Failed to close page")
                else:
                    raise ValueError(f"Unknown action type: {action.type}")
            except Exception as e:
                print(f"{RED}[DEBUG] Error during action {action.type}: {e}{RESET}")
                raise Exception(f"Failed to execute action: {action.type}")
        async def retry_get_dom(retries=3, delay=1):
            for attempt in range(retries):
                try:
                    return await self.get_current_dom()
                except Exception as e:
                    if attempt < retries - 1:
                        print(f"{RED}[DEBUG] Error getting DOM: {e}. Retrying...{RESET}")
                        await asyncio.sleep(delay)
                    else:
                        print(f"{RED}[DEBUG] Error getting DOM: {e}. No more retries.{RESET}")
                        raise Exception("Error: Unable to retrieve DOM")

        new_dom = await retry_get_dom()

        async def retry_get_url(retries=3, delay=1):
            for attempt in range(retries):
                try:
                    return await self.get_current_url()
                except Exception as e:
                    if attempt < retries - 1:
                        print(f"{RED}[DEBUG] Error getting URL: {e}. Retrying...{RESET}")
                        await asyncio.sleep(delay)
                    else:
                        print(f"{RED}[DEBUG] Error getting URL: {e}. No more retries.{RESET}")
                        raise Exception("Error: Unable to retrieve URL")

        new_url = await retry_get_url()
        async def retry_screenshot(retries=3, delay=1):
            for attempt in range(retries):
                try:
                    page = await browser_manager.get_current_page()
                    screenshot,new_img_path=await get_screenshot(page,task_id)
                    return screenshot,new_img_path
                except Exception as e:
                    if attempt < retries - 1:
                        print(f"{RED}[DEBUG] Error getting screenshot: {e}. Retrying...{RESET}")
                        await asyncio.sleep(delay)
                    else:
                        print(f"{RED}[DEBUG] Error getting screenshot: {e}. No more retries.{RESET}")
                        raise Exception(f"Failed to get screenshot")
                        

        new_base64_img,new_img_path = await retry_screenshot()

        return new_dom, new_url, new_base64_img,new_img_path
    

    async def get_current_dom(self) -> str:
        await wait_for_navigation()
        dom = await get_dom_with_content_type(content_type="all_fields")
        print(f"{CYAN}[DEBUG] Got current DOM (length: {len(dom)}){RESET}")
        return str(dom)

    async def get_current_url(self) -> str:
        # await wait_for_navigation()
        url = await geturl()
        print(f"{CYAN}[DEBUG] Got current URL: {url}{RESET}")
        return url


class BrowserMCTSSearchConfig(SearchConfig[BrowserState, BrowserAction, str]):
    def __init__(self, actor: BaseAgent, critic: BaseAgent, vision: BaseAgent,task_id:str) -> None:
        super().__init__()
        self.actor = actor
        self.critic = critic
        self.vision = vision
        self.task_id = task_id
        print(f"{BLUE}[DEBUG] BrowserMCTSSearchConfig initialized{RESET}")

    async def get_actions(self, state: BrowserState) -> List[BrowserAction]:
        print(f"{YELLOW}[DEBUG] Getting actions for current state{RESET}")
        if state is None:
            return []
        actor_input: AgentQActorInput = AgentQActorInput(
            objective=state.objective,
            completed_tasks=state.completed_tasks,
            current_web_text=state.web_text,
            current_base64_img=state.base64_img,
        )
        print(f"state.objective:{state.objective}")
        print(f"state.current_web_text:{state.web_text}")
        actor_output: AgentQActorOutput = await self.actor.run(actor_input)
        print(f"actor_output:{actor_output}")
        print(
            "--------------------------------------------------------------------------------"
        )
        proposed_tasks_with_actions: List[TaskWithActions] = actor_output.proposed_tasks
        print(f"proposed_tasks_with_actions:{proposed_tasks_with_actions}")
        print(
            "--------------------------------------------------------------------------------"
        )
        print(
            f"{CYAN}[DEBUG] Number of proposed tasks: {len(proposed_tasks_with_actions)}{RESET}"
        )
        print(
            f"{CYAN}[DEBUG] is_complete: {actor_output.is_complete}{RESET}"
        )
        if not actor_output.is_complete:
            ranked_actions = await self._rank_actions(
                state, proposed_tasks_with_actions
            )
            print(
                f"{CYAN}[DEBUG] Number of sorted actions: {len(ranked_actions)}{RESET}"
            )
        else :
            for task in proposed_tasks_with_actions:
                state.completed_tasks.append(task)
            ranked_actions = []
        return ranked_actions

    async def reward(
        self, state: BrowserState, action: BrowserAction, **kwargs
    ) -> Tuple[float, dict, bool]:
        print(f"completed_task_reward:{state.completed_tasks}")
        terminal_state = await is_terminal(
            state=state, vision=self.vision, critic=self.critic
        )
        if terminal_state:
            print(f"{GREEN}[DEBUG] Terminal state reached, reward: 1.0{RESET}")
            return 1.0, {}, True
        else:
            print(f"{RED}[DEBUG] Non-terminal state, reward: -0.01{RESET}")
            return -0.01, {}, False

    def fast_reward(
        self, state: BrowserState, action: BrowserAction
    ) -> tuple[float, dict]:
        return action.rank, {}

    # async def _rank_actions(
    #     self, state: BrowserState, tasks: List[TaskWithActions]
    # ) -> List[BrowserAction]:
    #     ranked_actions = []
    #     remaining_tasks = tasks.copy()
    #     total_tasks = len(remaining_tasks)
    #     print(f'completed_task_rankAction:{state.completed_tasks}')
    #     print(f"{GREEN}[INFO] Sorting task via Critic now...")
    #     for iteration in range(total_tasks):
    #         if not remaining_tasks:
    #             break

    #         critic_input = AgentQCriticInput(
    #             objective=state.objective,
    #             completed_tasks=state.completed_tasks,
    #             tasks_for_eval=remaining_tasks,
    #             current_base64_img=state.base64_img,
    #             current_web_text=state.web_text,
    #         )

    #         critic_output: AgentQCriticOutput = await self.critic.run(critic_input)
    #         top_task = critic_output.top_task

    #         if top_task and top_task.actions_to_be_performed:
    #             rank = 1.0 / (iteration + 1)  # Higher rank for earlier iterations
    #             ranked_actions.append(
    #                 BrowserAction(task_with_action=top_task, rank=rank)
    #             )

    #             # Remove the top task from remaining tasks
    #             remaining_tasks = [
    #                 task for task in remaining_tasks if task.id != top_task.id
    #             ]
    #         else:

    #             print(
    #                 f"{MAGENTA}[DEBUG] Warning: No valid top task found in iteration {iteration}. Skipping.{RESET}"
    #             )

    #     print(f"{CYAN}[DEBUG] Sorted actions.")
    #     return ranked_actions
    async def _rank_actions(
        self, state: BrowserState, tasks: List[TaskWithActions]
    ) -> List[BrowserAction]:
        ranked_actions = []
        remaining_tasks = tasks.copy()

        completed_tasks = state.completed_tasks
        origin_objective = state.objective
        print(f"completed_tasks:{completed_tasks}")
        description = ""
        is_first = True
        print(f"{GREEN}[INFO] Sorting task via Critic now...")
        for task in remaining_tasks:
            if not remaining_tasks:
                break

            critic_input = AgentQCriticInput(
                history_completed_tasks=state.completed_tasks,
                current_task=task,
                current_base64_img=state.base64_img,
            )

            critic_output: AgentQCriticOutput = await self.critic.run(critic_input)
            if is_first:
                description = critic_output.description
                is_first = False
            done_objective = critic_output.done_objective
            

            # 计算origin_objective和predict_objective之间的相似度

            check_input = VisionInput(
                origin_instruction=state.objective,
                done_description=description,
            )
            check_output: VisionOutput = await self.vision.run(check_input)
            matching_score = check_output.matching_score


            if matching_score :
                rank = (
                   matching_score
                )  # Higher rank for earlier iterations
                ranked_actions.append(BrowserAction(task_with_action=task, rank=rank))
            else:
                print(
                    f"{MAGENTA}[DEBUG] Warning: No valid  task found in remaining tasks. Skipping.{RESET}"
                )
            print("---------------------------------------------------------------")
        # 在循环结束后对ranked_actions按照rank降序排序
        ranked_actions.sort(key=lambda x: x.rank, reverse=True)
        print(f"{CYAN}[DEBUG] Sorted actions.")
        return ranked_actions


async def is_terminal(
    state: BrowserState, vision: BaseAgent, critic: BaseAgent
) -> bool:
    print(f"{YELLOW}[DEBUG] Checking if state is terminal{RESET}")
    screenshot, img_path = await get_screenshot()
    origin_objective = state.objective
    critic_input = AgentQCriticInput(
        history_completed_tasks=state.completed_tasks,
        current_task=None,
        current_base64_img=screenshot,
    )

    critic_output: AgentQCriticOutput = await critic.run(critic_input)

    description = critic_output.description
    done_objective = critic_output.done_objective
    state.done_objective = done_objective
    state.done_description = description
    # 计算origin_objective和predict_objective之间的相似度
    check_input = VisionInput(
        origin_instruction=state.objective,
        done_description=description,
    )
    check_output: VisionOutput = await vision.run(check_input)
    check_matching = check_output.matching_score
    terminal = check_matching > 0.85
    print(f"{YELLOW}[DEBUG] Output of vision LLM {terminal}{RESET}")
    return terminal


class BrowserMCTSWrapper(Reasoner[BrowserState, BrowserAction, str]):
    def __init__(
        self,
        objective: str,
        actor: BaseAgent,
        critic: BaseAgent,
        vision: BaseAgent,
        filter: BaseAgent,
        task_id: str,
        n_iterations: int = 1,
        depth_limit: int = 1,
        exploration_weight: float = 1.0,
    ):
        world_model = BrowserWorldModel(objective, vision, critic,task_id)
        search_config = BrowserMCTSSearchConfig(actor, critic, vision,task_id)
        search_algo = MCTS(
            n_iters=n_iterations,
            w_exp=exploration_weight,
            cum_reward=sum,
            calc_q=np.mean,
            simulate_strategy="max",
            output_strategy="max_reward",
            depth_limit=depth_limit,
        )
        super().__init__(world_model, search_config, search_algo)
        self.dpo_pairs = []
        print(
            f"{BLUE}[DEBUG] BrowserMCTSWrapper initialized with objective: {objective}{RESET}"
        )

    async def __call__(self) -> MCTSResult:
        print(f"{YELLOW}[DEBUG] Starting MCTS search{RESET}")
        result = await super().__call__("")
        return result

    @staticmethod
    def generate_dpo_pairs(result: MCTSResult) -> List[DPOPair]:
        dpo_pairs = []

        if result.trace_of_nodes is None or len(result.trace_of_nodes) < 2:
            print(f"{RED}[DEBUG] No valid path found{RESET}")
            return []

        print(f"{BLUE}[DEBUG] Printing rewards before generating dpo pairs")
        for i, node in enumerate(result.trace_of_nodes):
            print(f"{BLUE} {node.state.current_url} - {node.Q}")

        for i in range(len(result.trace_of_nodes) - 1):
            current_node = result.trace_of_nodes[i]
            next_node = result.trace_of_nodes[i + 1]

            if current_node.children:
                winning_action = next_node.action
                for child in current_node.children:
                    if child.action != winning_action:
                        dpo_pair = DPOPair(
                            state=DPOState(
                                dom=current_node.state.web_text[
                                    :1000
                                ],  # Truncate DOM to first 1000 characters
                                objective=current_node.state.objective,
                            ),
                            winning_action=DPOAction(
                                description=winning_action.task_with_action.description,
                                action=winning_action.task_with_action.actions_to_be_performed[
                                    0
                                ],
                            ),
                            losing_action=DPOAction(
                                description=child.action.task_with_action.description,
                                action=child.action.task_with_action.actions_to_be_performed[
                                    0
                                ],
                            ),
                        )
                        dpo_pairs.append(dpo_pair)

        return dpo_pairs
    @staticmethod
    def print_result(result: MCTSResult):
        if result.trace is None or len(result.trace) == 0:
            print(f"{RED}[DEBUG] No valid path found{RESET}")
            return
        states, actions = result.trace
        print(f"{GREEN}[DEBUG] Path found:{RESET}")
        for state, action in zip(states, actions):
            print(f"{CYAN}[DEBUG] Step {i}{RESET}")
            print(f"{CYAN}[DEBUG]  URL: {state.current_url}{RESET}")
            print(
                f"{CYAN}[DEBUG]  Action Type: {action.task_with_action.actions_to_be_performed[0].type}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Description: {action.task_with_action.description}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Detail: {action.task_with_action} - {action}{RESET}"
            )

        print(f"{GREEN}[DEBUG] Final URL: {states[-1].current_url}{RESET}")
        print(f"{GREEN}[DEBUG] Cumulative reward: {result.cum_reward}{RESET}")
        print(f"{GREEN}[DEBUG] Total steps: {len(actions)}{RESET}")
    
    @staticmethod
    def print_max_result(result: MCTSResult, task_id: str, file_path: str = None):
        if file_path is None:
            file_path = f"/dataset/wangzh/omni_dc/dlagent_result/optim3/{task_id}/success_result_output.json"
        with open(file_path, "w") as file:
            if result.trace is None or len(result.trace) == 0:
                json.dump({"debug": "No valid path found"}, file, indent=4)
                return
            states, actions = result.trace
            conversations = []
            images = []
            system_prompt: str = LLM_PROMPTS["AGENTQ_FINETUNE_PROMPT"]
            output = {
                "id": task_id,
                "conversations": [{"from": "system", "value": system_prompt}],
                "images": images
            }
            for i, (state, action) in enumerate(zip(states, actions)):
                input_data = AgentQActorInput(
                    objective=state.objective,
                    completed_tasks=state.completed_tasks,
                    current_web_text=state.web_text,
                    current_base64_img=state.img_path,
                )
                response = action.task_with_action
                messages = process_data(input_data, response)
                output["conversations"].extend(messages)
                images.append(state.img_path)

            json.dump(output, file, indent=4)

    
    @staticmethod
    def print_result(result: MCTSResult):
        if result.trace is None or len(result.trace) == 0:
            print(f"{RED}[DEBUG] No valid path found{RESET}")
            return
        states, actions = result.trace
        print(f"{GREEN}[DEBUG] Path found:{RESET}")
        for state, action in zip(states, actions):
            print(f"{CYAN}[DEBUG] Step {i}{RESET}")
            print(f"{CYAN}[DEBUG]  URL: {state.current_url}{RESET}")
            print(
                f"{CYAN}[DEBUG]  Action Type: {action.task_with_action.actions_to_be_performed[0].type}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Description: {action.task_with_action.description}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Detail: {action.task_with_action} - {action}{RESET}"
            )

        print(f"{GREEN}[DEBUG] Final URL: {states[-1].current_url}{RESET}")
        print(f"{GREEN}[DEBUG] Cumulative reward: {result.cum_reward}{RESET}")
        print(f"{GREEN}[DEBUG] Total steps: {len(actions)}{RESET}")

    # @staticmethod
    # def print_max_result(result: MCTSResult, task_id: str, file_path: str = None):
    #     if file_path is None:
    #         file_path = f"/dataset/wangzh/omni_dc/dlagent_result/{task_id}/maxReward_output.json"
    #     with open(file_path, "w") as file:
    #         if result.trace is None or len(result.trace) == 0:
    #             json.dump({"debug": "No valid path found"}, file, indent=4)
    #             return
    #         states, actions = result.trace
    #         conversations = []
    #         system_prompt: str = LLM_PROMPTS["AGENTQ_FINETUNE_PROMPT"]
    #         output = {
    #             "id": task_id,
    #             "conversations": [{"role": "system", "content": system_prompt}]
    #         }
    #         for i, (state, action) in enumerate(zip(states, actions)):
    #             input_data = AgentQActorInput(
    #                 objective=state.objective,
    #                 completed_tasks=state.completed_tasks,
    #                 current_web_text=state.web_text,
    #                 current_base64_img=state.img_path,
    #             )
    #             response = action.task_with_action
    #             messages = process_data(input_data, response)
    #             output["conversations"].extend(messages)
            

    #         json.dump(output, file, indent=4)


    @staticmethod
    async def filter_fail_result(result: MCTSResult, filter: BaseAgent):
        if result.fail_trace is None or len(result.fail_trace) == 0:
            print(f"{RED}[DEBUG] No valid path found{RESET}")
            return
        filtered_fail_trace = []
        useless_fail_trace = []
        for j, trace in enumerate(result.fail_trace):
            states, actions = trace
            if states:
                last_state = states[-1]
                fail_input: FailFilterInput = FailFilterInput(
                    objective=last_state.done_objective,
                    completed_tasks=last_state.completed_tasks,
                    current_base64_img=last_state.current_base64_img,
                    done_description=last_state.done_description,
                )
                fail_output: FailFilterOutput = await filter.run(fail_input)
                repeatability = fail_output.repeatability
                ineffectiveness = fail_output.ineffectiveness
                exploratory = fail_output.exploratory
                logicality = fail_output.logicality
                is_useless = fail_output.is_useless
                if not (repeatability > 0.5 or ineffectiveness > 0.5 or exploratory > 0.5 or logicality < 0.75 or is_useless):
                    filtered_fail_trace.append(trace)
                else:
                    useless_fail_trace.append(trace)

        result.fail_trace = filtered_fail_trace

        # 将useless_fail_trace存储到当前目录下的新建JSON文件中，每行一条轨迹
        useless_fail_trace_file = "useless_fail_trace.jsonl"
        with open(useless_fail_trace_file, "w", encoding="utf-8") as f:
            for trace in useless_fail_trace:
                json.dump(trace, f, ensure_ascii=False)
                f.write("\n")
        print(f"{GREEN}[DEBUG] Useless fail traces saved to {useless_fail_trace_file}{RESET}")
                    

    
    @staticmethod
    def print_fail_result(result: MCTSResult, task_id: str, file_path: str = None):
        if file_path is None:
            file_path = f"/dataset/wangzh/omni_dc/dlagent_result/optim3/{task_id}/fail_result_output.json"
        with open(file_path, "w") as file:
            if result.fail_trace is None or len(result.fail_trace) == 0:
                json.dump({"debug": "No valid path found"}, file, indent=4)
                return
            output = []
            system_prompt: str = LLM_PROMPTS["AGENTQ_FINETUNE_PROMPT"]
            for j, trace in enumerate(result.fail_trace):
                states, actions = trace
                conversations = [{"from": "system", "value": system_prompt}]
                images = []
                modify_objective=states[-1].done_objective
                for i, (state, action) in enumerate(zip(states, actions)):
                    input_data = AgentQActorInput(
                        objective=modify_objective,
                        completed_tasks=state.completed_tasks,
                        current_web_text=state.web_text,
                        current_base64_img="<image>",
                    )
                    response = action.task_with_action
                    messages = process_data(input_data, response)
                    conversations.extend(messages)
                    images.append(state.img_path)

                trace_output = {
                    "id": f"{task_id}_{j}",
                    "conversations": conversations,
                    "images": images
                }
                output.append(trace_output)

            json.dump(output, file, indent=4)

    # @staticmethod
    # def print_fail_result(result: MCTSResult, task_id: str, file_path: str = None):
    #     if file_path is None:
    #         file_path = f"/dataset/wangzh/omni_dc/dlagent_result/{task_id}/fail_result_output.json"
    #     with open(file_path, "w") as file:
    #         if result.fail_trace is None or len(result.fail_trace) == 0:
    #             json.dump({"debug": "No valid path found"}, file, indent=4)
    #             return
    #         output = []
    #         system_prompt: str = LLM_PROMPTS["AGENTQ_FINETUNE_PROMPT"]
    #         for j, trace in enumerate(result.fail_trace):
    #             states, actions = trace
    #             conversations = [{"role": "system", "content": system_prompt}]
    #             modify_objective=states[-1].done_objective
    #             for i, (state, action) in enumerate(zip(states, actions)):
    #                 input_data = AgentQActorInput(
    #                     objective=modify_objective,
    #                     completed_tasks=state.completed_tasks,
    #                     current_web_text=state.web_text,
    #                     current_base64_img=state.img_path,
    #                 )
    #                 response = action.task_with_action
    #                 messages = process_data(input_data, response)
    #                 conversations.extend(messages)
                
    #             trace_output = {
    #                 "id": f"{task_id}_{j}",
    #                 "conversations": conversations
    #             }
    #             output.append(trace_output)

    #         json.dump(output, file, indent=4)



    @staticmethod
    def print_dpo_pairs(dpo_pairs: List[DPOPair]):
        print(f"\n{MAGENTA}═══════════════ Generated DPO Pairs ═══════════════{RESET}")
        for i, dpo_pair in enumerate(dpo_pairs, 1):
            print(f"\n{CYAN}╔══ Pair {i} ══╗{RESET}")
            print(f"{YELLOW}┌─ State ─┐{RESET}")
            trimmed_dom = (
                dpo_pair.state.web_text[:100] + "..."
                if len(dpo_pair.state.web_text) > 100
                else dpo_pair.state.web_text
            )
            print(f"{YELLOW}│ DOM:{RESET} {trimmed_dom}")
            print(f"{GREEN}┌─ Winning Action ─┐{RESET}")
            print(f"{GREEN}│ Description:{RESET} {dpo_pair.winning_action.description}")
            print(f"{GREEN}│ Action Type:{RESET} {dpo_pair.winning_action.action.type}")
            print(f"{RED}┌─ Losing Action ─┐{RESET}")
            print(f"{RED}│ Description:{RESET} {dpo_pair.losing_action.description}")
            print(f"{RED}│ Action Type:{RESET} {dpo_pair.losing_action.action.type}")
            print(f"{CYAN}╚{'═' * (len('══ Pair X ══') - 2)}╝{RESET}")
        print(f"\n{MAGENTA}═══════════════ End of DPO Pairs ═══════════════{RESET}")

    @staticmethod
    async def write_dpo_pairs_to_file(dpo_pairs: List[DPOPair], filename: str):
        """
        Write the generated DPO pairs to a JSONL file in a format optimized for DPO training scripts.
        """
        with open(filename, "w") as f:
            for pair in dpo_pairs:
                dpo_entry = {
                    "prompt": f"Objective: {pair.state.objective}\nCurrent DOM: {pair.state.dom[:1000]}...",
                    "chosen": f"Action: {pair.winning_action.action.model_dump_json()}\nDescription: {pair.winning_action.description}",
                    "rejected": f"Action: {pair.losing_action.action.model_dump_json()}\nDescription: {pair.losing_action.description}",
                }
                json.dump(dpo_entry, f)
                f.write("\n")  # Add a newline for JSONL format

        print(f"{GREEN}[INFO] DPO pairs written to {filename} in JSONL format{RESET}")

    async def is_terminal(self, state: BrowserState) -> bool:
        print(f"{YELLOW}[DEBUG] Checking if state is terminal{RESET}")
        screenshot, img_path = await get_screenshot()
        origin_objective = state.objective
        critic_input = AgentQCriticInput(
            history_completed_tasks=state.completed_tasks,
            current_task=[],
            current_base64_img=screenshot,
        )

        critic_output: AgentQCriticOutput = await self.critic.run(critic_input)

        description = critic_output.description
        done_objective = critic_output.done_objective
        state.done_objective = done_objective
        state.done_description = description
        # 计算origin_objective和predict_objective之间的相似度
        check_input = VisionInput(
            origin_instruction=state.objective,
            done_description=description,
        )
        check_output: VisionOutput = await self.vision.run(check_input)
        check_matching=check_output.matching_score

        print(
            f"matching score : {check_matching}"
        )
        # similarity = jellyfish.jaro_winkler_similarity(origin_objective, predict_objective)

        terminal = check_matching > 0.85
        print(f"{YELLOW}[DEBUG] Output of vision LLM {terminal}{RESET}")
        return terminal


async def wait_for_navigation(max_retries=3):
    for attempt in range(max_retries):
        try:
            playwright_manager = PlaywrightManager()
            page = await playwright_manager.get_current_page()
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            print(
                f"{GREEN}[DEBUG] Navigation successful on attempt {attempt + 1}{RESET}"
            )
            return
        except Exception as e:
            print(
                f"{YELLOW}[DEBUG] Navigation error on attempt {attempt + 1}: {str(e)}{RESET}"
            )
    print(f"{RED}[DEBUG] Navigation failed after {max_retries} attempts{RESET}")


async def main(objective: str = None, eval_mode: bool = False, task_id: str = None,fail_path:str=None,success_path:str=None):
    print(f"{BLUE}Starting MCTS{RESET}")
    playwright_manager = PlaywrightManager()

    if not eval_mode:
        await playwright_manager.async_initialize()
    else:
        await playwright_manager.async_initialize(
            eval_mode=eval_mode, homepage="http://localhost:3000/abc"
        )
        page: Page = await playwright_manager.get_current_page()
        await page.set_extra_http_headers({"User-Agent": "AgentQ-Bot"})
    print(f"{GREEN}Browser started and ready{RESET}")

    print(f"{BLUE}[DEBUG] Starting main function{RESET}")
    actor = AgentQActor()
    critic = AgentQCritic()
    vision = VisionAgent()
    filter = FailFilter()

    print(f"{CYAN}[DEBUG] Objective set: {objective}{RESET}")

    browser_mcts_wrapper = BrowserMCTSWrapper(
        objective=objective,
        actor=actor,
        critic=critic,
        vision=vision,
        filter=filter,
        n_iterations=8,
        depth_limit=15,
        exploration_weight=1.0,
        task_id=task_id,
    )

    print(f"{YELLOW}[DEBUG] Running MCTS wrapper{RESET}")
    result = await browser_mcts_wrapper()

    # Print results
    print(f"{CYAN}[DEBUG] Printing MCTS result{RESET}")

    BrowserMCTSWrapper.print_max_result(result,task_id,success_path)
    BrowserMCTSWrapper.filter_fail_result(result,filter)
    BrowserMCTSWrapper.print_fail_result(result,task_id,fail_path)
            

    # # Tree visualization
    # # visualize(result=result)

    # # Dpo pairs
    # dpo_pairs = BrowserMCTSWrapper.generate_dpo_pairs(result=result)
    # BrowserMCTSWrapper.print_dpo_pairs(dpo_pairs=dpo_pairs)
    # await BrowserMCTSWrapper.write_dpo_pairs_to_file(
    #     dpo_pairs=dpo_pairs, filename="dpo_pairs.jsonl"
    # )
    # return dpo_pairs


# Temp class to write output to a file
class StreamToFile:
    def __init__(self, filename):
        self.file = open(filename, "w", buffering=1)

    def write(self, data):
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.file.flush()

    def close(self):
        self.file.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCTS with specified directory and log file.")
    parser.add_argument("--directory", type=str, required=True, help="The directory containing JSONL files.")
    parser.add_argument("--log_file", type=str, required=True, help="The log file to write completed tasks.")
    parser.add_argument("--fail_path", type=str, help="The file path to write the fail result output.")
    parser.add_argument("--success_path", type=str, help="The file path to write the maxreward result output.")
    args = parser.parse_args()

    directory = args.directory
    log_file = args.log_file
    fail_path = args.fail_path
    success_path = args.success_path

    print(f"{BLUE}[DEBUG] Script started{RESET}")
    completed_tasks = []

    try:
        # 遍历指定目录下的所有 .jsonl 文件
        jsonl_files = [f for f in os.listdir(directory) if f.endswith('.jsonl')]
        print(f"{CYAN}[DEBUG] Found JSONL files: {jsonl_files}{RESET}")

        for jsonl_file in jsonl_files:
            jsonl_file_path = os.path.join(directory, jsonl_file)
            # 读取每个 .jsonl 文件中的数据
            with open(jsonl_file_path, "r", encoding="utf-8") as f:
                tasks = [json.loads(line) for line in f]

            # 遍历所有任务并执行 main 函数
            for task in tasks:
                ques = task["ques"]
                task_id = task["id"]
                website = task["web"]
                objective = f"{ques} {website}"
                print(f"{CYAN}[DEBUG] Objective set: {objective}{RESET}")
                print(f"{CYAN}[DEBUG] task_id: {task_id}{RESET}")

                asyncio.run(
                    main(
                        objective=objective,
                        eval_mode=False,
                        task_id=task_id,
                        fail_path=fail_path,
                        success_path=success_path,
                    )
                )
                completed_tasks.append(task_id)

    finally:
        with open(log_file, "w") as f:
            for task_id in completed_tasks:
                f.write(f"{task_id}\n")

    print(f"{GREEN}[DEBUG] Script finished{RESET}")