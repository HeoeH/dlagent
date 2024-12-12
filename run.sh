#!/bin/bash

# 设置默认的目录名称
DIRECTORY=${1:-"IL_1"}

# 运行第一个命令
python -m agentq.core.mcts.mcts_data --directory data_webvoyager_training/$DIRECTORY --log_file completed_tasks_optim_$DIRECTORY.log --fail_path result/$DIRECTORY --success_path result/$DIRECTORY --n_iteration 5 --depth_limit 10

# 运行第二个命令
python -m agentq.core.mcts.mcts_data --directory data_webvoyager_training/optim_iter2 --log_file completed_tasks_optim_iter2.log --fail_path result/optim_iter2 --success_path result/optim_iter2 --n_iteration 7 --depth_limit 15