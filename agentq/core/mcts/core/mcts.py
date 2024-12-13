import itertools
import math
import os
import json
from abc import ABC
from collections import defaultdict
from copy import deepcopy
from typing import Callable, Generic, Hashable, NamedTuple, Optional
from agentq.core.models.models import STOPAction 
from agentq.core.prompts.prompts import LLM_PROMPTS
from agentq.core.models.models import   AgentQActorInput
from agentq.core.skills.process_data import process_data
import numpy as np
import copy
from tqdm import trange
# ANSI color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
from agentq.core.mcts.core.base import (
    Action,
    Example,
    SearchAlgorithm,
    SearchConfig,
    State,
    Trace,
    WorldModel,
)
from agentq.core.web_driver.playwright import PlaywrightManager


class MCTSNode(Generic[State, Action, Example]):
    id_iter = itertools.count()

    @classmethod
    def reset_id(cls):
        cls.id_iter = itertools.count()

    def __init__(
        self,
        state: Optional[State],
        action: Optional[Action],
        parent: "Optional[MCTSNode]" = None,
        fast_reward: float = 0.0,
        fast_reward_details=None,
        is_terminal: bool = False,
        calc_q: Callable[[list[float]], float] = np.mean,
    ):
        """
        A node in the MCTS search tree

        :param state: the current state
        :param action: the action of the last step, i.e., the action from parent node to current node
        :param parent: the parent node, None if root of the tree
        :param fast_reward: an estimation of the reward of the last step
        :param is_terminal: whether the current state is a terminal state
        :param calc_q: the way to calculate the Q value from histories. Defaults: np.mean
        """
        self.id = next(MCTSNode.id_iter)
        if fast_reward_details is None:
            fast_reward_details = {}
        self.cum_rewards: list[float] = []
        self.fast_reward = self.reward = fast_reward
        self.fast_reward_details = fast_reward_details
        self.is_terminal = is_terminal
        self.action = action
        self.state = state
        self.parent = parent
        self.children: "Optional[list[MCTSNode]]" = None
        self.calc_q = calc_q
        self.N = 0  # Visit count
        self._Q = 0  # Reward
        if parent is None:
            self.depth = 0
        else:
            self.depth = parent.depth + 1

    def __str__(self):
        return f"MCTSNode(id={self.id}, state={self.state}, action={self.action}, reward={self.reward}, is_terminal={self.is_terminal})"

    # noinspection PyPep8Naming
    # @property
    # def Q(self) -> float:
    #     if self.state is None:
    #         return self.fast_reward
    #     else:
    #         return self.calc_q(self.cum_rewards)

    @property
    def Q(self) -> float:
        if self.N == 0:
            return 0
        return self._Q  # Getter

    @Q.setter
    def Q(self, value: float):
        self._Q = value  # Setter


class MCTSResult(NamedTuple):
    terminal_state: State
    cum_reward: float
    trace: list[Trace]
    trace_of_nodes: list[MCTSNode]
    tree_state: MCTSNode
    trace_in_each_iter: list[list[MCTSNode]] = None
    fail_trace:list[Trace]=None
    tree_state_after_each_iter: list[MCTSNode] = None
    aggregated_result: Optional[Hashable] = None


class MCTSAggregation(Generic[State, Action, Example], ABC):
    def __init__(
        self, retrieve_answer: Callable[[State], Hashable], weight_policy: str = "edge"
    ):
        assert weight_policy in ["edge", "edge_inverse_depth", "uniform"]
        self.retrieve_answer = retrieve_answer
        self.weight_policy = weight_policy

    def __call__(
        self, tree_state: MCTSNode[State, Action, Example]
    ) -> Optional[Hashable]:
        answer_dict = defaultdict(lambda: 0)

        def visit(cur: MCTSNode[State, Action, Example]):
            if cur.state is None:
                return []
            if cur.is_terminal:
                answer = self.retrieve_answer(cur.state)
                if answer is None:
                    print("MCTSAggregation: no answer retrieved.")
                    return []
                if self.weight_policy == "edge":
                    answer_dict[answer] += cur.reward
                elif self.weight_policy == "edge_inverse_depth":
                    answer_dict[answer] += cur.reward / cur.depth
                elif self.weight_policy == "uniform":
                    answer_dict[answer] += 1.0
                return [(answer, cur.depth)]
            depth_list = defaultdict(list)
            cur_list = []
            for child in cur.children:
                cur_list.extend(child_info := visit(child))
                for answer, depth in child_info:
                    depth_list[answer].append(depth)
            for answer, depths in depth_list.items():
                if self.weight_policy == "edge":
                    answer_dict[answer] += cur.reward
                elif self.weight_policy == "edge_inverse_depth":
                    answer_dict[answer] += cur.reward / np.mean(depths)
            return cur_list

        visit(tree_state)

        if len(answer_dict) == 0:
            return None
        return max(answer_dict, key=lambda answer: answer_dict[answer])


class MCTS(SearchAlgorithm, Generic[State, Action, Example]):
    def __init__(
        self,
        output_trace_in_each_iter: bool = True,
        w_exp: float = 1.0,
        depth_limit: int = 5,
        n_iters: int = 5,
        task_id: str = None,
        cum_reward: Callable[[list[float]], float] = sum,
        calc_q: Callable[[list[float]], float] = np.mean,
        simulate_strategy: str | Callable[[list[float]], int] = "random",
        output_strategy: str = "max_reward",
        uct_with_fast_reward: bool = True,
        aggregator: Optional[MCTSAggregation] = None,
        disable_tqdm: bool = True,
        node_visualizer: Callable[[MCTSNode], dict] = lambda x: x.__dict__,
    ):
        """
        MCTS algorithm

        :param output_trace_in_each_iter: whether to output the trace of the chosen trajectory in each iteration ; the trace is *deepcopy*-ed
                                          will also output *tree_state_after_each_iter*, which is the *deepcopy*-ed root
        :param w_exp: the weight of exploration in UCT
        :param cum_reward: the way to calculate the cumulative reward from each step. Defaults: sum
        :param calc_q: the way to calculate the Q value from histories. Defaults: np.mean
        :param simulate_strategy: simulate strategy. Options: 'max', 'sample', 'random', or use a custom function
        :param output_strategy: the way to output the result. The nodes are not *deepcopy*-ed, so the information is after all iterations
                                Options: 'max_reward': dfs on the final tree to find a trajectory with max reward using :param cum_reward:
                                         'follow_max': starting from root, choose the maximum reward child at each step. May output a non-terminal node if dead end
                                         'max_visit': the terminal node with maximum number of visits
                                         'max_iter': the trajectory with a terminal node and max reward among those in each iteration
                                         'last_iter': the last trajectory. May output a non-terminal node if the last iteration leads to a dead end
                                         'last_terminal_iter': the last trajectory with a terminal node
                                Outputs *None* if no trajectory with terminal node but required
        :param uct_with_fast_reward: if True, use fast_reward instead of reward for unvisited children in UCT
                                     Otherwise, visit the *unvisited* children with maximum fast_reward first
        """
        super().__init__()
        self.world_model = None
        self.search_config = None
        self.output_trace_in_each_iter = output_trace_in_each_iter
        self.w_exp = w_exp
        self.task_id = task_id
        self.depth_limit = depth_limit
        self.n_iters = n_iters
        self.cum_reward = cum_reward
        self.calc_q = calc_q
        default_simulate_strategies: dict[str, Callable[[list[float]], int]] = {
            "max": lambda x: np.argmax(x),
            "sample": lambda x: np.random.choice(len(x), p=x),
            "random": lambda x: np.random.choice(len(x)),
        }
        self.simulate_choice: Callable[[list[float]], int] = (
            default_simulate_strategies.get(simulate_strategy, simulate_strategy)
        )
        assert output_strategy in [
            "max_reward",
            "follow_max",
            "max_visit",
            "max_iter",
            "last_iter",
            "last_terminal_iter",
        ]
        self.output_strategy = output_strategy
        self.uct_with_fast_reward = uct_with_fast_reward
        self._output_iter: list[MCTSNode] = None
        self._next_reward_iter: list[MCTSNode] = None
        self._follow_reward_iter: list[MCTSNode] = None
        self._follow_cum_reward = -math.inf
        self._next_cum_reward = -math.inf
        self._output_cum_reward = -math.inf
        self.trace_in_each_iter: list[list[MCTSNode]] = None
        self.root: Optional[MCTSNode] = None
        self.disable_tqdm = disable_tqdm
        self.node_visualizer = node_visualizer
        self.aggregator = aggregator
        self.node_visualizer = node_visualizer
        self.aggregator = aggregator

    async def iterate(self, node: MCTSNode) -> list[MCTSNode]:
        path = await self._select(node)
        print("Selected Node")
        print("------------------------------------------------------------")
        if not self._is_terminal_with_depth_limit(path[-1]):
            flag,result_child=await self._expand(path[-1])
            print(f"result_child:{result_child}")
            await self._simulate(path)
        cum_reward = self._back_propagate(path)
        #self._print_tree(self.root)
        if (
            self.output_strategy == "max_iter"
            and path[-1].is_terminal
            and cum_reward > self._output_cum_reward
        ):
            self._output_cum_reward = cum_reward
            self._output_iter = path
        if self.output_strategy == "last_iter":
            self._output_cum_reward = cum_reward
            self._output_iter = path
        if self.output_strategy == "last_terminal_iter" and path[-1].is_terminal:
            self._output_cum_reward = cum_reward
            self._output_iter = path
        return path


    def _is_terminal_with_depth_limit(self, node: MCTSNode):
        return node.is_terminal or node.depth >= self.depth_limit

    def _print_tree(self, node: MCTSNode, depth: int = 0):
        indent = "  " * depth
        url = node.state.url if node.state and hasattr(node.state, "url") else "N/A"
        print(f"{indent}URL: {url}, Q: {node.Q:.4f}, N: {node.N}")
        if node.children:
            for child in node.children:
                self._print_tree(child, depth + 1)

    async def _select(self, node: MCTSNode) -> list[MCTSNode]:
        path = []
        while True:
            path.append(node)
            if (
                node.children is None
                or len(node.children) == 0
                or self._is_terminal_with_depth_limit(node)
            ):
                return path
            node = self._uct_select(node)
            flag=True
            try:
                flag,result_child=await self.world_model.step(node.parent.state, node.action)
            except Exception as e:
                print(f"Exception during world_model.step:{e},retry..")
                try:
                    flag,result_child=await self.world_model.step(node.parent.state, node.action)
                except  Exception as e:
                    if not flag or not result_child:
                        node.N=1000
                        await self._select(self.root)
                        

           

    # def _uct(self, node: MCTSNode) -> float:
    #     return node.Q + self.w_exp * np.sqrt(
    #         np.log(len(node.parent.cum_rewards)) / max(1, len(node.cum_rewards))
    #     )

    def _uct(self, node: MCTSNode) -> float:
        return node.Q + self.w_exp * math.sqrt(math.log(node.parent.N) / (1 + node.N))

    # def _uct_select(self, node: MCTSNode) -> MCTSNode:
    #     if self.uct_with_fast_reward or all(x.state is not None for x in node.children):
    #         return max(node.children, key=self._uct)
    #     else:
    #         unvisited_children = filter(lambda x: x.state is None, node.children)
    #         return max(unvisited_children, key=lambda x: x.fast_reward)

    def _uct_select(self, node: MCTSNode) -> MCTSNode:
        # First, check for unvisited nodes
        for child in node.children:
            if child.N == 0:
                return child

        # If all nodes have been visited, use the UCB1 formula
        return max(node.children, key=self._uct)

    async def _expand(self, node: MCTSNode) -> bool:
        print("Expanding node")
        flag = True
        if node.state is None:
            try:
                node.state, aux = await self.world_model.step(
                    node.parent.state, node.action
                )
            # reward is calculated after the state is updated, so that the
            # information can be cached and passed from the world model
            # to the reward function with **aux without repetitive computation
                node.reward, node.fast_reward_details, node.is_terminal = await self.search_config.reward(
                    node.state, node.action, **node.fast_reward_details
                )
            # node.is_terminal = await self.world_model.is_terminal(node.state)
            except Exception as e:
                print(f"Exception during world_model.step: {e}")
                flag = False
        if node.is_terminal:
            return flag, False

        children = []
        # print(node.state.url)
        # print(node)
        if flag:
            actions = await self.search_config.get_actions(node.state)
        else:
           node.fast_reward=-1
           return flag,False
        print("Got possible actions")
        if len(actions) == 1 and len(actions[0].task_with_action.actions_to_be_performed) == 1 and isinstance(actions[0].task_with_action.actions_to_be_performed[0], STOPAction):
            node.reward, node.reward_details, node.is_terminal = await self.search_config.reward(
                node.state, node.action, **node.fast_reward_details
            )
            child = MCTSNode(
                state=None,
                action=actions[0],
                parent=node,
                fast_reward=node.reward,
                fast_reward_details={},
                calc_q=self.calc_q,
            )
            node.children = children

            return flag, False

        for action in actions:
            fast_reward, fast_reward_details = self.search_config.fast_reward(
                node.state, action
            )
            child = MCTSNode(
                state=None,
                action=action,
                parent=node,
                fast_reward=fast_reward,
                fast_reward_details=fast_reward_details,
                calc_q=self.calc_q,
            )
            children.append(child)

        node.children = children
        return flag, True

    # async def _expand(self, node: MCTSNode) -> bool:
    #     print("Expanding node")
    #     flag = True
    #     if node.state is None:
    #         try:
    #             node.state, aux = await self.world_model.step(
    #                 node.parent.state, node.action
    #             )
    #             print(f"Node state_IMG:{node.state.img_path}")

    #         # reward is calculated after the state is updated, so that the
    #         # information can be cached and passed from the world model
    #         # to the reward function with **aux without repetitive computation
    #             node.reward, node.fast_reward_details, node.is_terminal = await self.search_config.reward(
    #                 node.state, node.action, **node.fast_reward_details
    #             )
    #         # node.is_terminal = await self.world_model.is_terminal(node.state)
    #         except Exception as e:
    #             print(f"Exception during world_model.step: {e}")
    #             flag = False
    #     if node.is_terminal:
    #         return flag, False

    #     children = []
    #     # print(node.state.url)
    #     # print(node)
    #     if flag:
    #         actions = await self.search_config.get_actions(node.state)
    #     else:
    #         if node.parent and hasattr(node.parent, 'children'):
    #             if node in node.parent.children:
    #                 node.parent.children.remove(node)
    #                 print(f"Node removed from parent's children list")
    #             else:
    #                 print(f"Node not found in parent's children list")
    #             return flag, False
    #         else:
    #             print(f"Parent node or children list not found")
    #             return flag, False
    #     print("Got possible actions")
    #     if len(actions) == 1 and len(actions[0].task_with_action.actions_to_be_performed) == 1 and isinstance(actions[0].task_with_action.actions_to_be_performed[0], STOPAction):
    #         node.reward, node.reward_details, node.is_terminal = await self.search_config.reward(
    #             node.state, node.action, **node.fast_reward_details
    #         )
    #         child = MCTSNode(
    #             state=None,
    #             action=actions[0],
    #             parent=node,
    #             fast_reward=node.reward,
    #             fast_reward_details={},
    #             calc_q=self.calc_q,
    #         )
    #         node.children = children

    #         return flag, False

    #     for action in actions:
    #         fast_reward, fast_reward_details = self.search_config.fast_reward(
    #             node.state, action
    #         )
    #         child = MCTSNode(
    #             state=None,
    #             action=action,
    #             parent=node,
    #             fast_reward=fast_reward,
    #             fast_reward_details=fast_reward_details,
    #             calc_q=self.calc_q,
    #         )
    #         children.append(child)

    #     node.children = children
    #     return flag, True


    async def _simulate(self, path: list[MCTSNode]):
        print("Simulating the node")
        node = path[-1]
        while True:
            flag = True
            result_child = True
            if node.state is None:
                flag,result_child=await self._expand(node) 
                if flag:
                    print(f"node.action.task_with_action:{node.action.task_with_action}")
                    path.append(node)
                else:
                    self._simulate(path)
                print(f"result_child:{result_child}")
                print(f"flag:{flag}")  
            print(f"node.depth:{node.depth}")
            print(f"self._is_terminal_with_depth_limit(node){self._is_terminal_with_depth_limit(node)}")
            if self._is_terminal_with_depth_limit(node) or not result_child:
                return
            fast_rewards = [child.fast_reward for child in node.children]
            count = 0
            for fast_reward in fast_rewards:
                if fast_reward < 0:
                    count += 1
                if count >= 3:
                    return
            node = node.children[self.simulate_choice(fast_rewards)]

            

    # def _back_propagate(self, path: list[MCTSNode]):D
    #     rewards = []
    #     cum_reward = -math.inf
    #     for node in reversed(path):
    #         rewards.append(node.reward)
    #         cum_reward = self.cum_reward(rewards[::-1])
    #         node.cum_rewards.append(cum_reward)
    #     return cum_reward

    def _print_success_result(self, path: list[MCTSNode], file_path: str = None):
        task_id=self.task_id
        if file_path is None:
            file_path = f"result/IL_1/{task_id}/success_iter_output.json"
        else:
            file_path = os.path.join(file_path, f"{task_id}/success_iter_output.json")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 读取现有内容或初始化
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                output = json.load(file)
        else:
            output = []

        trace_success = (
            [node.state for node in path],
            [node.action for node in path],
        )
        system_prompt: str = LLM_PROMPTS["AGENTQ_FINETUNE_PROMPT"]
        states, actions = trace_success
        # 打印 states 和 actions 的长度
        print(f"Length of states: {len(states)}")
        print(f"Length of actions: {len(actions)}")
        conversations = [{"from": "system", "value": system_prompt}]
        images = []
        for i, (state, action) in enumerate(zip(states, actions)):
            if action is None or not hasattr(action, 'task_with_action'):
                print(f"Warning: action or action.task_with_action is None or missing at index {i}")
                continue
            print(f"action.task_with_action:{action.task_with_action}")
            input_data = AgentQActorInput(
                objective=state.objective,
                completed_tasks=state.completed_tasks,
                current_web_text=state.web_text,
                current_base64_img="<image>",
            )
            response = action.task_with_action
            messages = process_data(input_data, response)
            conversations.extend(messages)
            images.append(state.img_path)

        trace_output = {
            "id": f"{task_id}_success_iter_{i}",
            "conversations": conversations,
            "images": images
        }
        output.append(trace_output)

        # 写入文件
        with open(file_path, "w") as file:
            json.dump(output, file, indent=4)
    def _back_propagate(self, path: list[MCTSNode]):
        reward = path[-1].reward
        if path[-1].is_terminal:
            path_tmp = copy.deepcopy(path)
            trace_success = (
                [node.state for node in path_tmp],
                [node.action for node in path_tmp],
            )
            self._print_success_result(path_tmp)
            
        for node in reversed(path):
            if node.state is None:
                continue
            print(f'node.Q:{node.Q}')
            print(f'node.N:{node.N}')
            node.Q = (node.Q * node.N + reward) / (node.N + 1)
            node.N += 1
            print("--updated--")
            print(f'node.newQ:{node.Q}')
            print(f'node.newN:{node.N}')
        return path[0].Q  # Return the root node's updated Q-value
    
    def _dfs_next_reward(self, path: list[MCTSNode]) -> tuple[float, list[MCTSNode]]:
        cur = path[-1]
        if cur.is_terminal:
            reward = self.cum_reward([node.reward for node in path[1:]])
            return reward, path
        if cur.children is None:
            return -math.inf, path
        visited_children = [x for x in cur.children if x.state is not None]
        if len(visited_children) == 0:
            return -math.inf, path
            
        # 收集所有可能的路径和奖励
        all_paths = []
        for child in visited_children:
            reward, child_path = self._dfs_next_reward(path + [child])
            if reward != -math.inf:  # 只保存有效路径
                all_paths.append((reward, child_path))
        
        # 根据奖励排序
        sorted_paths = sorted(all_paths, key=lambda x: x[0], reverse=True)
        
        # 返回次优路径（如果存在）
        if len(sorted_paths) >= 2:
            return sorted_paths[1]  # 返回第二高奖励的路径
        elif len(sorted_paths) == 1:
            return -math.inf, path  # 如果只有一条路径，返回该路径
        else:
            return -math.inf, path  # 如果没有有效路径，返回默认值


    def _dfs_max_reward(self, path: list[MCTSNode]) -> tuple[float, list[MCTSNode]]:
        cur = path[-1]
        if cur.is_terminal:
            return self.cum_reward([node.reward for node in path[1:]]), path
        if cur.children is None:
            return -math.inf, path
        visited_children = [x for x in cur.children if x.state is not None]
        if len(visited_children) == 0:
            return -math.inf, path
        return max(
            (self._dfs_max_reward(path + [child]) for child in visited_children),
            key=lambda x: x[0],
        )

    async def search(self):
        self._output_cum_reward = -math.inf
        self._output_iter = None
        self.root = MCTSNode(
            state=await self.world_model.init_state(),
            action=None,
            parent=None,
            calc_q=self.calc_q,
        )
        if self.output_trace_in_each_iter:
            self.trace_in_each_iter = []

        for iter in trange(
            self.n_iters, disable=self.disable_tqdm, desc="MCTS iteration", leave=False
        ):
            print(f"-----iter: {iter}----")
            # start with home page for each iteration
            playwright_manager = PlaywrightManager()
            await playwright_manager.go_to_homepage()
            path = await self.iterate(self.root)
            if self.output_trace_in_each_iter:
                if not path[-1].is_terminal:
                    self.trace_in_each_iter.append(deepcopy(path))


        # if self.output_strategy == "follow_max":
        if self.output_strategy == "max_reward":
            self._follow_reward_iter = []
            cur = self.root
            while True:
                self._follow_reward_iter.append(cur)
                if cur.is_terminal:
                    break
                visited_children = [x for x in cur.children if x.state is not None]
                if len(visited_children) == 0:
                    break
                cur = max(visited_children, key=lambda x: x.reward)
            self._follow_cum_reward = self.cum_reward(
                [node.reward for node in self._follow_reward_iter[1::-1]]
            )
            if self._follow_cum_reward == -math.inf:
                self._follow_reward_iter = None
            if self._follow_reward_iter is None:
                print(f"{RED}self._follow_reward_iter is None")
        if self.output_strategy == "max_reward":
            self._output_cum_reward, self._output_iter = self._dfs_max_reward(
                [self.root]
            )
            if self._output_cum_reward == -math.inf:
                self._output_iter = None
            if self._output_iter is None:
                print(f"{RED}self._output_iter is None")
        if self.output_strategy == "max_reward":
            self._next_cum_reward, self._next_reward_iter = self._dfs_next_reward(
                [self.root]
            )
            if self._next_cum_reward == -math.inf:
                self._next_reward_iter = None
            if self._next_reward_iter is None:
                print(f"{RED}self._next_reward_iter is None")

    async def __call__(
        self,
        world_model: WorldModel[State, Action, Example],
        search_config: SearchConfig[State, Action, Example],
        log_file: Optional[str] = None,
        **kwargs,
    ) -> MCTSResult:
        MCTSNode.reset_id()
        self.world_model = world_model
        self.search_config = search_config

        await self.search()
        trace=[]
        if self._output_iter is None:
            terminal_state = trace_max = None
        else:
            terminal_state = self._output_iter[-1].state
            trace_max = (
                [node.state for node in self._output_iter],
                [node.action for node in self._output_iter[1:]],
            )
        if trace_max is None:
            print(f"{RED}trace_max is None")
        else:
            trace.append(trace_max)


        if self._next_reward_iter is None:
            terminal_next_state = trace_next = None
        else:
            terminal_next_state = self._next_reward_iter[-1].state
            trace_next = (
                [node.state for node in self._next_reward_iter],
                [node.action for node in self._next_reward_iter[1:]],
            )
        if trace_next is None:
            print(f"{RED}trace_next is None")
        else:
            trace.append(trace_next)
            
        
        if self._follow_reward_iter is None:
            terminal_follow_state = trace_follow = None
        else:
            terminal_follow_state = self._follow_reward_iter[-1].state
            trace_follow = (
                [node.state for node in self._follow_reward_iter],
                [node.action for node in self._follow_reward_iter[1:]],
            )
        if trace_follow is None:
            print(f"{RED}trace_follow is None")
        else:
            trace.append(trace_follow)
        

        trace_in_each_iter = self.trace_in_each_iter
        fail_trace = []
        if trace_in_each_iter:
            for path_f in trace_in_each_iter:
                trace_f=(
                    [node.state for node in path_f],
                    [node.action for node in path_f[1:]],
                )
                fail_trace.append(trace_f)

        self.fail_trace=fail_trace
        if self.output_trace_in_each_iter:
            trace_in_each_iter = self.trace_in_each_iter
            tree_state_after_each_iter = [trace[0] for trace in trace_in_each_iter]
        else:
            trace_in_each_iter = tree_state_after_each_iter = None
        
        result = MCTSResult(
            terminal_state=terminal_state,
            cum_reward=self._output_cum_reward,
            trace=trace,
            trace_of_nodes=self._output_iter,
            tree_state=self.root,
            trace_in_each_iter=trace_in_each_iter,
            fail_trace=self.fail_trace,
            tree_state_after_each_iter=tree_state_after_each_iter,
        )
        if self.aggregator is not None:
            result = MCTSResult(
                terminal_state=result.terminal_state,
                cum_reward=result.cum_reward,
                trace=result.trace,
                trace_of_nodes=result.trace_of_nodes,
                tree_state=result.tree_state,
                trace_in_each_iter=result.trace_in_each_iter,
                tree_state_after_each_iter=result.tree_state_after_each_iter,
                aggregated_result=self.aggregator(result.tree_state),
            )
        return result
