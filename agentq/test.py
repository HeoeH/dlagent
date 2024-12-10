from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

from agentq.core.models.models import (
    AgentQActorInput,
)
from agentq.core.prompts.prompts import LLM_PROMPTS

# Default: Load the model on the available device(s)
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-7B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)

processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
objective = "Find the cheapest premium economy flights from Helsinki to Stockholm on 15 March on Skyscanner."
completed_tasks = None
current_web_text = "[1]: <a> 'Gmail ';      [2]: <a> '搜索图片 ';   [3]: <a> 'Google 应用'; [4]: <a> 'Google 账号： heoeh (heoeh95@gmail.com)';     [5]: <textarea> 'q';    [7]: <div> '按语音搜索';        [8]: <div> '按图搜索';  [9]: <input> 'btnK';    [10]: <input> 'btnI';   [11]: <a> 'English';    [12]: <a> '关于 Google';        [13]: <a> '广告';       [14]: <a> '商务';       [15]: <a> 'Google 搜索的运作方式';     [16]: <a> '隐私权';      [17]: <a> '条款';       [18]: <div> '设置';"

actor_input: AgentQActorInput = AgentQActorInput(
    objective=objective,
    completed_tasks=completed_tasks,
    current_web_text=current_web_text,
    current_base64_img="././result/screenshot_20241124_202730.png",
)
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "././result/screenshot_20241124_202730.png",
            },
            {
                "type": "text",
                "text": actor_input.model_dump_json(exclude={"current_base64_img"}),
            },
        ],
    }
]


system_prompt: str = LLM_PROMPTS["AGENTQ_ACTOR_PROMPT"]
messages.append({"role": "system", "content": system_prompt})

print(messages)
# Preparation for inference
text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
image_inputs, video_inputs = process_vision_info(messages)
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
inputs = inputs.to("cuda")

# Inference: Generation of the output
generated_ids = model.generate(**inputs, max_new_tokens=1000000)

generated_ids_trimmed = [
    out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
)
print(output_text)
# <|object_ref_start|>language switch<|object_ref_end|><|box_start|>(576,12),(592,42)<|box_end|><|im_end|>

import json

# 假设生成的文本是一个 JSON 格式的字符串
try:
    output_dict = json.loads(output_text[0])
    print(json.dumps(output_dict, indent=2))
except json.JSONDecodeError as e:
    print(f"JSON 解码错误: {e}")
    print(f"生成的文本: {output_text[0]}")
