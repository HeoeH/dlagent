import json
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

# 读取 JSON 文件中的 messages
file_path = "result/Apple--33/maxReward_output.json"
with open(file_path, "r") as file:
    data = json.load(file)
    messages = data["conversations"]

# 打印读取的 messages
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
# <|object_ref_start|>language switch<|object_ref_end|><|box_start|>(576,12),(592,42)<|box_end|>import json
