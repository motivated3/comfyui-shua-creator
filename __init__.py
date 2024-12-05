import server
from aiohttp import web, ClientSession
import multidict
import folder_paths
import os
import base64
import json
import logging
import subprocess

WEB_DIRECTORY = "entry"
NODE_CLASS_MAPPINGS = {}
__all__ = ['NODE_CLASS_MAPPINGS']
version = "V1.0.0"

logging.info(f"### Loading: Inner Enhance ({version})")
workspace_path = os.path.join(os.path.dirname(__file__))
comfy_path = os.path.dirname(folder_paths.__file__)
db_dir_path = os.path.join(workspace_path, "db")

dist_path = os.path.join(workspace_path, 'dist/inner_enhance_web')
if os.path.exists(dist_path):
    server.PromptServer.instance.app.add_routes([
        web.static('/inner_enhance_web/', dist_path),
    ])

BACKUP_DIR = os.path.join(workspace_path, "backup")
MAX_BACKUP_FILES = 20


@server.PromptServer.instance.routes.route('*', '/api/dm/{tail:.*}')
async def proxy_handler(request):
    try:
        HOST = "online.miaoshuaai.com"
        original_path = request.match_info['tail']
        logging.info(f"original_path: {original_path}")
        target_path = f'https://{HOST}/api/dm/{original_path}'
        # 模拟浏览器请求头
        headers = {
            "Host": HOST,
            "Origin": f"https://{HOST}",
            "Referer": f"https://{HOST}",
        }

        # 复制请求中的其他头部信息
        headers.update({key: value for key, value in request.headers.items() if key not in headers})
        # logging.info(f"headers: {headers}")

        async with ClientSession() as session:
            if request.method == 'GET':
                params = request.query
                async with session.get(target_path, headers=headers, params=params) as resp:
                    logging.info(f"resp.status: {resp.status}")
                    if resp.status == 401:
                        return web.Response(status=401, text="Unauthorized")
                    outgoing_headers = multidict.CIMultiDict(resp.headers)
                    if 'Content-Encoding' in outgoing_headers:
                        outgoing_headers.popall('Content-Encoding')
                    # outgoing_headers.popall('Content-Encoding')
                    response = web.StreamResponse(
                        status=resp.status, headers=outgoing_headers)
                    await response.prepare(request)
                    async for data in resp.content.iter_any():
                        await response.write(data)
                    await response.write_eof()
            elif request.method == 'POST':
                data = await request.read()
                async with session.post(target_path, headers=headers, data=data) as resp:
                    logging.info(f"resp.status: {resp.status}")
                    if resp.status == 401:
                        return web.Response(status=401, text="Unauthorized")
                    outgoing_headers = multidict.CIMultiDict(resp.headers)
                    outgoing_headers.popall('Content-Encoding')
                    response = web.StreamResponse(
                        status=resp.status, headers=outgoing_headers)
                    await response.prepare(request)
                    async for data in resp.content.iter_any():
                        await response.write(data)
                    await response.write_eof()
            elif request.method == 'DELETE':
                data = await request.read()
                async with session.delete(target_path, headers=headers, data=data) as resp:
                    logging.info(f"resp.status: {resp.status}")
                    outgoing_headers = multidict.CIMultiDict(resp.headers)
                    outgoing_headers.popall('Content-Encoding')
                    response = web.StreamResponse(
                        status=resp.status, headers=outgoing_headers)
                    await response.prepare(request)
                    async for data in resp.content.iter_any():
                        await response.write(data)
                    await response.write_eof()

            return response
    except Exception as e:
        logging.error(f"🔴🔴Error proxy_handler {e}")
        return web.Response(text=json.dumps({"error": str(e)}), status=500)

def get_git_info(repo_path):
    """获取指定 Git 仓库的远程地址和当前版本号"""
    try:
        # 获取远程地址
        remote_url = subprocess.check_output(
            ['git', '-C', repo_path, 'config', '--get', 'remote.origin.url'],
            stderr=subprocess.STDOUT
        ).strip().decode('utf-8')

        # 获取当前版本号（commit hash）
        commit_hash = subprocess.check_output(
            ['git', '-C', repo_path, 'rev-parse', 'HEAD'],
            stderr=subprocess.STDOUT
        ).strip().decode('utf-8')

        return remote_url, commit_hash
    except subprocess.CalledProcessError:
        return None, None

def scan_git_repos(root_dir):
    git_info_list = []

    for root, dirs, files in os.walk(root_dir, followlinks=True):
        if '.git' in dirs:
            repo_path = os.path.abspath(root)
            remote_url, commit_hash = get_git_info(repo_path)
            if remote_url and commit_hash:
                git_info_list.append((repo_path, remote_url, commit_hash))
            dirs.remove('.git')  # 不再递归进入 .git 目录

    return git_info_list

@server.PromptServer.instance.routes.get("/inner/enhance/node_git")
async def node_git(request):
    try:
        pwd = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
        logging.info(f'start walk from {pwd}')
        git_info_list = scan_git_repos(pwd)
        byte_data = json.dumps(git_info_list).encode('utf-8')
        base64_bytes = base64.b64encode(byte_data)
        base64_string = base64_bytes.decode('utf-8')
        return web.Response(text=base64_string, content_type='application/json')
    except Exception as e:
        logging.error(f"🔴🔴Error node_git {e}")
        return web.Response(text=json.dumps({"error": str(e)}), status=500)
