import re

path = '/home/azim/ai-call-platform/fazle-ai/docker-compose.yaml'
with open(path) as f:
    content = f.read()
content = content.replace('USE_LLM_GATEWAY: "true"', 'USE_LLM_GATEWAY: "false"')
with open(path, 'w') as f:
    f.write(content)
count = content.count('USE_LLM_GATEWAY: "false"')
print(f"Replaced USE_LLM_GATEWAY to false ({count} occurrences)")
