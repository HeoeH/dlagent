import gzip
import shutil

# 源文件路径
source_file = 'C:\\Users\\yjh\\Desktop\\cjh\\WebVoyager\\WebVoyager\\core\\models\\GoogleNews-vectors-negative300.bin.gz'
# 目标文件路径
destination_file = 'C:\\Users\\yjh\\Desktop\\cjh\\WebVoyager\\WebVoyager\\core\\models\\GoogleNews-vectors-negative300.bin'

# 解压文件
with gzip.open(source_file, 'rb') as f_in:
    with open(destination_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

# print("File decompressed successfully.")

# import requests

# url = 'https://github.com/mmihaltz/word2vec-GoogleNews-vectors/raw/master/GoogleNews-vectors-negative300.bin.gz'
# local_filename = 'GoogleNews-vectors-negative300.bin.gz'

# with requests.get(url, stream=True) as r:
#     r.raise_for_status()
#     with open(local_filename, 'wb') as f:
#         for chunk in r.iter_content(chunk_size=8192):
#             f.write(chunk)

# print("File downloaded successfully.")