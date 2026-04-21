import jsonschema
import json
import sys

# 加载 schema 文件
with open('schemas/tool.gaode.poi_around.json', 'r', encoding='utf-8') as f:
    schema = json.load(f)

# 取出 input_schema 和 output_schema
input_schema = schema['input_schema']
output_schema = schema['output_schema']
examples = schema.get('examples', {})

# 测试输入
input_data = examples['input']
output_success = examples['output_success']
output_error = examples['output_error']

def validate(data, schema, label):
    try:
        jsonschema.validate(instance=data, schema=schema)
        print(f'{label} 校验通过')
    except jsonschema.ValidationError as e:
        print(f'{label} 校验失败:', e)
        sys.exit(1)

# 校验输入
validate(input_data, input_schema, '输入示例')
# 校验输出（成功）
validate(output_success, output_schema, '输出成功示例')
# 校验输出（失败）
validate(output_error, output_schema, '输出失败示例')

print('全部自动化测试通过！')
