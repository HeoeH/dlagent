from playwright.async_api import async_playwright
import asyncio
from playwright.async_api import Page
from agentq.core.web_driver.playwright import PlaywrightManager
import asyncio
import json
import sys
from typing import List, Tuple

import numpy as np
from langsmith import traceable
from playwright.async_api import Page

from agentq.core.agent.agentq_actor import AgentQActor
from agentq.core.agent.agentq_critic import AgentQCritic
from agentq.core.agent.base import BaseAgent
from agentq.core.agent.vision_agent import VisionAgent
from agentq.core.mcts.core.base import Reasoner, SearchConfig, WorldModel
from agentq.core.mcts.core.mcts import MCTS, MCTSResult
from agentq.core.mcts.visualization.visualizer_client import visualize
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
)
from agentq.core.skills.click_using_selector import click
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import EnterTextEntry, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.highlight_interactive_elements import highlight_interactive_elements
from agentq.core.skills.get_screenshot import get_screenshot
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.web_driver.playwright import PlaywrightManager

# ANSI color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"


@traceable(run_type="chain", name="mcts")
class BrowserWorldModel(WorldModel[BrowserState, BrowserAction, str]):
    def __init__(self, objective: str, vision: BaseAgent) -> None:
        super().__init__()
        self.objective = objective
        self.vision = vision
        print(
            f"{BLUE}[DEBUG] BrowserWorldModel initialized with objective: {self.objective}{RESET}"
        )
    

    
    async def init_state(self) -> BrowserState:
        # go to home page
        print(f"{GREEN}[DEBUG] GOING TO INIT STATE HOMEPAGE{RESET}")
        playwright_manager = PlaywrightManager()
        await playwright_manager.go_to_homepage()

        # initialzie dom and url
        initial_dom = await self.get_current_dom()
        initial_url = await self.get_current_url()
        print(f"{GREEN}[DEBUG] Initial state created - URL: {initial_url}{RESET}")

        return BrowserState(
            dom=initial_dom,
            url=initial_url,
            objective=self.objective,
            completed_tasks=[],
        )

    async def step(
        self, state: BrowserState, browser_action: BrowserAction
    ) -> Tuple[BrowserState, dict]:
        print(f"{YELLOW}[DEBUG] Executing step with action: {browser_action}{RESET}")
        new_dom, new_url = await self.execute_browser_action(browser_action)
        current_task = browser_action.task_with_action
        new_completed_tasks = state.completed_tasks + [current_task]
        new_state = BrowserState(
            dom=new_dom,
            url=new_url,
            objective=state.objective,
            completed_tasks=new_completed_tasks,
        )
        print(f"{GREEN}[DEBUG] New state after step - URL: {new_url}{RESET}")
        return new_state, {}

    async def is_terminal(self, state: BrowserState) -> bool:
        terminal = await is_terminal(state, self.vision)
        print(f"{CYAN}[DEBUG] is_terminal: {terminal}{RESET}")
        return terminal

    async def execute_browser_action(
        self, browser_action: BrowserAction
    ) -> Tuple[str, str]:
        action = browser_action.task_with_action.actions_to_be_performed[0]
        print(f"{YELLOW}[DEBUG] Executing browser action: {action.type}{RESET}")

        if action.type == ActionType.GOTO_URL:
            print(f"{CYAN}[DEBUG] Trying to go to url{RESET}")
            await openurl(url=action.website, timeout=action.timeout or 1)
            print(f"{CYAN}[DEBUG] Went to url{RESET}")
        elif action.type == ActionType.TYPE:
            entry = EnterTextEntry(
                query_selector=f"[mmid='{action.mmid}']",
                text=action.content,
            )
            await entertext(entry)
            # await wait_for_navigation()
            print(f"{CYAN}[DEBUG] Typed text into element{RESET}")
        elif action.type == ActionType.CLICK:
            await click(
                selector=f"[mmid='{action.mmid}']",
                wait_before_execution=action.wait_before_execution or 2,
            )
            print(f"{CYAN}[DEBUG] Clicked element{RESET}")
        elif action.type == ActionType.ENTER_TEXT_AND_CLICK:
            await enter_text_and_click(
                text_selector=f"[mmid='{action.text_element_mmid}']",
                text_to_enter=action.text_to_enter,
                click_selector=f"[mmid='{action.click_element_mmid}']",
                wait_before_click_execution=action.wait_before_click_execution or 2,
            )
            # await wait_for_navigation()
            print(f"{CYAN}[DEBUG] Entered text and clicked element{RESET}")

        try:
            new_dom = await self.get_current_dom()
        except Exception as e:
            print(f"{RED}[DEBUG] Error getting DOM after action: {e}{RESET}")
            new_dom = "Error: Unable to retrieve DOM"

        try:
            new_url = await self.get_current_url()
        except Exception as e:
            print(f"{RED}[DEBUG] Error getting URL after action: {e}{RESET}")
            new_url = "Error: Unable to retrieve URL"

        print(f"{GREEN}[DEBUG] After action execution - New URL: {new_url}{RESET}")
        return new_dom, new_url

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
    def __init__(self, actor: BaseAgent, critic: BaseAgent, vision: BaseAgent) -> None:
        super().__init__()
        self.actor = actor
        self.critic = critic
        self.vision = vision
        print(f"{BLUE}[DEBUG] BrowserMCTSSearchConfig initialized{RESET}")

    async def get_actions(self, state: BrowserState) -> List[BrowserAction]:
        print(f"{YELLOW}[DEBUG] Getting actions for current state{RESET}")
        actor_input: AgentQActorInput = AgentQActorInput(
            objective=state.objective,
            completed_tasks=state.completed_tasks,
            current_web_text=state.web_text,
            current_base64_img=state.base64_img,
        )
        actor_output: AgentQActorOutput = await self.actor.run(actor_input)

        proposed_tasks_with_actions: List[TaskWithActions] = actor_output.proposed_tasks
        print(
            f"{CYAN}[DEBUG] Number of proposed tasks: {len(proposed_tasks_with_actions)}{RESET}"
        )

        ranked_actions = await self._rank_actions(state, proposed_tasks_with_actions)
        print(f"{CYAN}[DEBUG] Number of sorted actions: {len(ranked_actions)}{RESET}")

        return ranked_actions

    async def reward(
        self, state: BrowserState, action: BrowserAction, **kwargs
    ) -> Tuple[float, dict]:
        terminal_state = await is_terminal(state=state, vision=self.vision)
        if terminal_state:
            print(f"{GREEN}[DEBUG] Terminal state reached, reward: 1.0{RESET}")
            return 1.0, {}
        else:
            print(f"{RED}[DEBUG] Non-terminal state, reward: -0.01{RESET}")
            return -0.01, {}

    def fast_reward(
        self, state: BrowserState, action: BrowserAction
    ) -> tuple[float, dict]:
        return action.rank, {}

    async def _rank_actions(
        self, state: BrowserState, tasks: List[TaskWithActions]
    ) -> List[BrowserAction]:
        ranked_actions = []
        remaining_tasks = tasks.copy()
        total_tasks = len(remaining_tasks)

        print(f"{GREEN}[INFO] Sorting task via Critic now...")
        for iteration in range(total_tasks):
            if not remaining_tasks:
                break

            critic_input = AgentQCriticInput(
                objective=state.objective,
                completed_tasks=state.completed_tasks,
                tasks_for_eval=remaining_tasks,
                current_page_url=state.url,
                current_page_dom=state.dom,
            )

            critic_output: AgentQCriticOutput = await self.critic.run(critic_input)
            top_task = critic_output.top_task

            if top_task and top_task.actions_to_be_performed:
                rank = 1.0 / (iteration + 1)  # Higher rank for earlier iterations
                ranked_actions.append(
                    BrowserAction(task_with_action=top_task, rank=rank)
                )

                # Remove the top task from remaining tasks
                remaining_tasks = [
                    task for task in remaining_tasks if task.id != top_task.id
                ]
            else:
                print(
                    f"{MAGENTA}[DEBUG] Warning: No valid top task found in iteration {iteration}. Skipping.{RESET}"
                )

        print(f"{CYAN}[DEBUG] Sorted actions.")
        return ranked_actions


async def is_terminal(state: BrowserState, vision: BaseAgent) -> bool:
    print(f"{YELLOW}[DEBUG] Checking if state is terminal{RESET}")
    screenshot = await get_screenshot()
    vision_input: VisionInput = VisionInput(objective=state.objective)
    vision_output: VisionOutput = await vision.run(
        vision_input, screenshot, model="gpt-4o-2024-08-06"
    )
    print(f"{YELLOW}[DEBUG] Output of vision LLM {vision_output.is_terminal}{RESET}")
    return vision_output.is_terminal


class BrowserMCTSWrapper(Reasoner[BrowserState, BrowserAction, str]):
    def __init__(
        self,
        objective: str,
        actor: BaseAgent,
        critic: BaseAgent,
        vision: BaseAgent,
        n_iterations: int = 1,
        depth_limit: int = 1,
        exploration_weight: float = 1.0,
    ):
        world_model = BrowserWorldModel(objective, vision)
        search_config = BrowserMCTSSearchConfig(actor, critic, vision)
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
            print(f"{BLUE} {node.state.url} - {node.Q}")

        for i in range(len(result.trace_of_nodes) - 1):
            current_node = result.trace_of_nodes[i]
            next_node = result.trace_of_nodes[i + 1]

            if current_node.children:
                winning_action = next_node.action
                for child in current_node.children:
                    if child.action != winning_action:
                        dpo_pair = DPOPair(
                            state=DPOState(
                                dom=current_node.state.dom[
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
        for i, (state, action) in enumerate(zip(states, actions)):
            print(f"{CYAN}[DEBUG] Step {i}{RESET}")
            print(f"{CYAN}[DEBUG]  URL: {state.url}{RESET}")
            print(
                f"{CYAN}[DEBUG]  Action Type: {action.task_with_action.actions_to_be_performed[0].type}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Description: {action.task_with_action.description}{RESET}"
            )
            print(
                f"{CYAN}[DEBUG]  Action Detail: {action.task_with_action} - {action}{RESET}"
            )

        print(f"{GREEN}[DEBUG] Final URL: {states[-1].url}{RESET}")
        print(f"{GREEN}[DEBUG] Cumulative reward: {result.cum_reward}{RESET}")
        print(f"{GREEN}[DEBUG] Total steps: {len(actions)}{RESET}")

    @staticmethod
    def print_dpo_pairs(dpo_pairs: List[DPOPair]):
        print(f"\n{MAGENTA}═══════════════ Generated DPO Pairs ═══════════════{RESET}")
        for i, dpo_pair in enumerate(dpo_pairs, 1):
            print(f"\n{CYAN}╔══ Pair {i} ══╗{RESET}")
            print(f"{YELLOW}┌─ State ─┐{RESET}")
            trimmed_dom = (
                dpo_pair.state.dom[:100] + "..."
                if len(dpo_pair.state.dom) > 100
                else dpo_pair.state.dom
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
        screenshot = await get_screenshot()
        vision_input: VisionInput = VisionInput(objective=state.objective)
        vision_output: VisionOutput = await self.vision.run(
            vision_input, screenshot, model="gpt-4o-2024-08-06"
        )
        print(
            f"{YELLOW}[DEBUG] Output of vision LLM {vision_output.is_terminal}{RESET}"
        )
        return vision_output.is_terminal


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


async def main(objective: str = None, eval_mode: bool = False):
    print(f"{BLUE}Starting MCTS{RESET}")
    playwright_manager = PlaywrightManager()

    # 初始化 PlaywrightManager
    if not eval_mode:
        await playwright_manager.async_initialize()
    else:
        await playwright_manager.async_initialize(
            eval_mode=eval_mode, homepage="http://localhost:3000/abc"
        )
    dom = await get_dom_with_content_type(content_type="all_fields")
    # print(f"{CYAN}[DEBUG] Got current DOM (length: {len(dom)}){RESET}")
    print(str(dom))

    # 获取当前页面对象
    page: Page = await playwright_manager.get_current_page()
    screenshot,img_path= await get_screenshot()
    print(f'screenshot:{screenshot}')
    # await highlight_interactive_elements(page)
    
    if eval_mode:
        await page.set_extra_http_headers({"User-Agent": "AgentQ-Bot"})

    print(f"{GREEN}Browser started and ready{RESET}")

    # # 调用 get_web_element_rect 函数
    # rects, web_eles, web_eles_text = await get_web_element_rect(page, fix_color=True)   
    # print(f'web_eles_text:')
    # print(web_eles_text)
    # print(f'web_ele:{web_eles}')
    # # print(f'rects:')
    # # print(type(rects))

    # return web_eles_text
    # print(f"{BLUE}[DEBUG] Starting main function{RESET}")
    # actor = AgentQActor()
    # critic = AgentQCritic()
    # vision = VisionAgent()

    # print(f"{CYAN}[DEBUG] Objective set: {objective}{RESET}")

    # browser_mcts_wrapper = BrowserMCTSWrapper(
    #     objective=objective,
    #     actor=actor,
    #     critic=critic,
    #     vision=vision,
    #     n_iterations=10,
    #     depth_limit=6,
    #     exploration_weight=1.0,
    # )

    # print(f"{YELLOW}[DEBUG] Running MCTS wrapper{RESET}")
    # result = await browser_mcts_wrapper()

    # # Print results
    # print(f"{CYAN}[DEBUG] Printing MCTS result{RESET}")
    # BrowserMCTSWrapper.print_result(result)

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
async def get_web_element_rect(page, fix_color=True):
    # 定义 borderColor 变量
    borderColor = 'red'  # 默认边框颜色

    if fix_color:
        borderColor = 'blue'  # 如果 fix_color 为 True，则设置边框颜色为蓝色
        selected_function = "getFixedColor"
    else:
        selected_function = "getRandomColor"

    js_script = """
    let labels = [];

        function markPage() {
            var bodyRect = document.body.getBoundingClientRect();

            var items = Array.prototype.slice.call(
                document.querySelectorAll('*')
            ).map(function(element) {
                var vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
                var vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
                
                var rects = [...element.getClientRects()].filter(bb => {
                var center_x = bb.left + bb.width / 2;
                var center_y = bb.top + bb.height / 2;
                var elAtCenter = document.elementFromPoint(center_x, center_y);

                return elAtCenter === element || element.contains(elAtCenter) 
                }).map(bb => {
                const rect = {
                    left: Math.max(0, bb.left),
                    top: Math.max(0, bb.top),
                    right: Math.min(vw, bb.right),
                    bottom: Math.min(vh, bb.bottom)
                };
                return {
                    ...rect,
                    width: rect.right - rect.left,
                    height: rect.bottom - rect.top
                }
                });

                var area = rects.reduce((acc, rect) => acc + rect.width * rect.height, 0);

                return {
                element: element,
                include: 
                    (element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT") ||
                    (element.tagName === "BUTTON" || element.tagName === "A" || (element.onclick != null) || window.getComputedStyle(element).cursor == "pointer") ||
                    (element.tagName === "IFRAME" || element.tagName === "VIDEO" || element.tagName === "LI" || element.tagName === "TD" || element.tagName === "OPTION")
                ,
                area,
                rects,
                text: element.textContent.trim().replace(/\s{2,}/g, ' '),
                tagName: element.tagName,
                type: element.getAttribute("type") || '',
                ariaLabel: element.getAttribute("aria-label") || ''
                };
            }).filter(item =>
                item.include && (item.area >= 20)
            );

            // Only keep inner clickable items
            // first delete button inner clickable items
            const buttons = Array.from(document.querySelectorAll('button, a, input[type="button"], div[role="button"]'));

            //items = items.filter(x => !buttons.some(y => y.contains(x.element) && !(x.element === y) ));
            items = items.filter(x => !buttons.some(y => items.some(z => z.element === y) && y.contains(x.element) && !(x.element === y) ));
            items = items.filter(x => 
                !(x.element.parentNode && 
                x.element.parentNode.tagName === 'SPAN' && 
                x.element.parentNode.children.length === 1 && 
                x.element.parentNode.getAttribute('role') &&
                items.some(y => y.element === x.element.parentNode)));

            items = items.filter(x => !items.some(y => x.element.contains(y.element) && !(x == y)))

            // Function to generate random colors
            function getRandomColor(index) {
                var letters = '0123456789ABCDEF';
                var color = '#';
                for (var i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
                }
                return color;
            }

            function getFixedColor(index) {
                var color = '#000000'
                return color
            }
            //function getFixedColor(index){
            //    var colors = ['#FF0000', '#00FF00', '#0000FF', '#000000']; // Red, Green, Blue, Black
            //    return colors[index % 4];
            //}
            

            // Lets create a floating border on top of these elements that will always be visible
            items.forEach(function(item, index) {
                item.rects.forEach((bbox) => {
                newElement = document.createElement("div");
                var borderColor = COLOR_FUNCTION(index);
                newElement.style.outline = `2px dashed ${borderColor}`;
                newElement.style.position = "fixed";
                newElement.style.left = bbox.left + "px";
                newElement.style.top = bbox.top + "px";
                newElement.style.width = bbox.width + "px";
                newElement.style.height = bbox.height + "px";
                newElement.style.pointerEvents = "none";
                newElement.style.boxSizing = "border-box";
                newElement.style.zIndex = 2147483647;
                // newElement.style.background = `${borderColor}80`;
                
                // Add floating label at the corner
                var label = document.createElement("span");
                label.textContent = index;
                label.style.position = "absolute";
                //label.style.top = "-19px";
                label.style.top = Math.max(-19, -bbox.top) + "px";
                //label.style.left = "0px";
                label.style.left = Math.min(Math.floor(bbox.width / 5), 2) + "px";
                label.style.background = borderColor;
                label.style.color = "white";
                label.style.padding = "2px 4px";
                label.style.fontSize = "12px";
                label.style.borderRadius = "2px";
                newElement.appendChild(label);
                
                document.body.appendChild(newElement);
                labels.push(newElement);
                // item.element.setAttribute("-ai-label", label.textContent);
                });
            })

            // For the first way
            // return [labels, items.map(item => ({
            //     rect: item.rects[0] // assuming there's at least one rect
            // }))];

            // For the second way
            return [labels, items]
        }

    // Call the markPage function and return its result
    markPage();
    """.replace("COLOR_FUNCTION", selected_function)

    # 获取 web 元素的矩形和其他属性  
    rects, items_raw = await page.evaluate(js_script)  

    format_ele_text = []  
    for web_ele_id in range(len(items_raw)):  

        element_info = items_raw[web_ele_id]
        ele_tag_name = element_info['tagName']
        ele_type = element_info['type']
        ele_aria_label = element_info['ariaLabel']
        # print(f"tagname:{ele_tag_name}")
        # print(f"type:{ele_type}")
        # print(f"ariaLabel:{ele_aria_label}")

        # 安全地访问 tag_name  
        # ele_tag_name = items_raw[web_ele_id]['element'].tag_name  
        # ele_type = items_raw[web_ele_id]['element'].get_attribute("type")  
        # ele_aria_label = items_raw[web_ele_id]['element'].get_attribute("aria-label")  
        label_text = items_raw[web_ele_id]['text']  
        input_attr_types = ['text', 'search', 'password', 'email', 'tel']  
        
        if not label_text:  
            if (ele_tag_name.lower() == 'input' and ele_type in input_attr_types) or \
            ele_tag_name.lower() == 'textarea' or \
            (ele_tag_name.lower() == 'button' and ele_type in ['submit', 'button']):  
                if ele_aria_label:  
                    format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{ele_aria_label}\";")  
                else:  
                    format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";")  
        elif label_text and len(label_text) < 200:  
            if not ("<img" in label_text and "src=" in label_text):  
                if ele_tag_name in ["button", "input", "textarea"]:  
                    if ele_aria_label and (ele_aria_label != label_text):  
                        format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\", \"{ele_aria_label}\";")  
                    else:  
                        format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";")  
                else:  
                    if ele_aria_label and (ele_aria_label != label_text):  
                        format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\", \"{ele_aria_label}\";")  
                    else:  
                        format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\";")  

    format_ele_text = '\t'.join(format_ele_text)  
    return rects, [web_ele['element'] for web_ele in items_raw], format_ele_text


if __name__ == "__main__":
    print(f"{BLUE}[DEBUG] Script started{RESET}")
    output_stream = StreamToFile("output.txt")
    # sys.stdout = output_stream
    # sys.stderr = output_stream
    try:
        asyncio.run(
            main(
                objective="Find a family-friendly hotel in NYC with a rating of 4 stars or higher on https://www.nyc.com",
                eval_mode=False,
            )
        )
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        output_stream.close()
    print(f"{GREEN}[DEBUG] Script finished{RESET}")


# # 示例运行
# async def main(eval_mode: bool = False):
#     playwright_manager = PlaywrightManager()
#     await playwright_manager.go_to_homepage()

#     # 调用get_web_element_rect函数
#     labels, items = await get_web_element_rect(page, fix_color=True)

#     print(f"Number of marked elements: {len(items)}")
#     for item in items:
#         print(f"Element text: {item['text']}")


# # 运行示例
# asyncio.run(main())