"""Browsing-first layout. Diagnostic tables stay outside the main workspace."""
import gradio as gr

CSS = """
.gradio-container {max-width:1600px!important;background:#f7f8fa}
#workspace {align-items:flex-start;gap:20px}
#sidebar {background:white;border:1px solid #e4e7ec;border-radius:16px;padding:16px}
#details {background:white;border:1px solid #e4e7ec;border-radius:16px;padding:18px}
#asset-grid {border-radius:16px}
#asset-grid .caption {white-space:pre-line!important;line-height:1.45!important;max-height:5em!important;font-size:12px}
@media(max-width:900px){#workspace{flex-direction:column}#sidebar,#details{width:100%!important}}
"""


def build_workbench(library, indexer, callbacks, tag_names):
    def browse(query='', media_type='全部', tag='全部', keyword='', limit=20):
        if query.strip():
            gallery, scores, message, refs = callbacks['search'](query, limit, media_type, tag)
            if keyword.strip():
                keep = [i for i, r in enumerate(refs) if keyword.lower().strip() in library.get_asset(r['id'])['original_name'].lower()]
                gallery, refs = [gallery[i] for i in keep], [refs[i] for i in keep]
            return gallery, refs, f'搜索：{query} · 类型：{media_type} · 标签：{tag} · 显示 {len(refs)} 项\n{message}'
        assets = library.list_assets(media_type={'图片':'image', '视频':'video'}.get(media_type), keyword=keyword)
        gallery, refs = [], []
        for asset in assets:
            item = library.get_asset(asset['id'])['items'][0]
            if tag != '全部' and tag not in item['tags']:
                continue
            searchable = item['embedding_status'] == 'ready' and item['embedding_model'] == indexer.encoder.model_id and item['embedding_revision'] == indexer.encoder.revision
            state = '可搜索' if searchable else '索引待处理'
            if item['caption_status'] == 'processing':
                state += ' · 正在生成标签'
            elif item['caption_status'] == 'failed':
                state += ' · 描述失败'
            elif item['caption_status'] != 'ready' and asset['media_type'] == 'image':
                state += ' · 标签待生成'
            kind = '图片' if asset['media_type'] == 'image' else f"视频 · {asset['duration_ms']/1000:.0f} 秒"
            tags = '、'.join(item['tags'][:2])
            gallery.append((str(library.root / item['preview_path']), f"{asset['original_name']}\n{kind} · {state}" + (f' · {tags}' if tags else '')))
            refs.append({'id': asset['id']})
        empty = '暂无符合条件的素材；可清除筛选或导入素材。' if not refs else '点击素材查看预览、描述与下载。'
        return gallery, refs, f'浏览 · 类型：{media_type} · 标签：{tag} · {len(refs)} 项\n{empty}'

    def upload_files(paths):
        return library.import_files(paths or [])

    def index_all():
        try:
            yield from indexer.index_pending()
        except Exception as exc:
            yield str(exc)

    def retry_one(selected):
        if not selected:
            yield '请先选择素材。'
            return
        try:
            yield from indexer.index_pending(selected)
        except Exception as exc:
            yield str(exc)

    with gr.Blocks(title='ObjectLift · 素材工作台', theme=gr.themes.Soft(primary_hue='indigo'), css=CSS, head='<link rel="icon" type="image/png" href="/favicon.ico">') as page:
        gr.HTML('<header style="display:flex;align-items:center;gap:12px;padding:8px 0 20px"><img src="/brand/objectlift-icon-concept-v1.png" alt="ObjectLift 图标" width="56" height="56"><div><strong style="font-size:26px">ObjectLift</strong><div>用画面找到灵感，让素材随手可用。</div></div><a href="/" style="margin-left:auto;color:#6366f1">返回首页 ↗</a></header>')
        selected, refs, frame_refs = gr.State(None), gr.State([]), gr.State([])
        with gr.Tabs():
            with gr.Tab('素材工作台'):
                with gr.Row():
                    query = gr.Textbox(placeholder='描述要找的画面，例如：树林中的小路', label='搜索素材', scale=7)
                    search = gr.Button('搜索', variant='primary', scale=1)
                    clear = gr.Button('清除搜索', scale=1)
                with gr.Accordion('＋ 导入图片或视频', open=False):
                    files = gr.File(label='拖入或选择文件 · 图片20MB · H.264视频300MB / 4分钟', file_count='multiple', file_types=['.jpg','.jpeg','.png','.mp4'])
                    gr.Markdown('导入后即可浏览。需要搜索时建立索引，需要标签时生成描述；本阶段尚未自动串联处理。')
                    upload = gr.Button('导入素材', variant='primary')
                    import_report = gr.JSON(label='导入结果')
                with gr.Row(elem_id='workspace'):
                    with gr.Column(scale=1, min_width=180, elem_id='sidebar'):
                        gr.Markdown('### 浏览素材')
                        kind = gr.Radio(['全部','图片','视频'], value='全部', label='素材类型')
                        tag = gr.Dropdown(['全部', *tag_names], value='全部', label='标签（图片）')
                        keyword = gr.Textbox(label='文件名包含')
                        refresh = gr.Button('刷新素材')
                        with gr.Accordion('搜索设置', open=False):
                            limit = gr.Slider(1,50,value=20,step=1,label='最多返回')
                            gr.Markdown('首次搜索需要加载模型；可提前预热。搜索按相似程度排序，不代表准确率。')
                            warmup = gr.Button('预热搜索')
                        with gr.Accordion('处理任务', open=False):
                            index = gr.Button('建立索引 / 重试失败项')
                            gr.Markdown('标签批量补齐位于诊断页。')
                    with gr.Column(scale=4, min_width=360):
                        summary = gr.Textbox(label='当前视图', interactive=False, lines=2)
                        gallery = gr.Gallery(label='素材', columns=3, height=600, type='filepath', elem_id='asset-grid', allow_preview=False)
                    with gr.Column(scale=2, min_width=300, elem_id='details'):
                        gr.Markdown('### 素材详情')
                        preview = gr.Image(label='画面预览', type='filepath', interactive=False, height=240)
                        player = gr.HTML()
                        description = gr.Textbox(label='AI 描述与标签 · 请核对画面', lines=6, interactive=False, show_copy_button=True)
                        download = gr.File(label='下载原文件', interactive=False)
                        with gr.Accordion('视频抽样帧 · 点击定位', open=False):
                            frames = gr.Gallery(columns=3, label='时间轴', type='filepath', allow_preview=False)
                        with gr.Accordion('更多操作与文件信息', open=False):
                            describe = gr.Button('生成 / 重新生成描述与标签')
                            retry = gr.Button('重试此素材索引')
                            detail = gr.Textbox(label='文件信息', interactive=False, lines=8)
                task = gr.Textbox(label='处理状态', value='暂无运行中的任务', interactive=False)
            with gr.Tab('诊断与批量处理'):
                gr.Markdown('### 标签覆盖检查\n这里可以区分未生成、失败和未分类；标签数量允许重叠。')
                category = gr.Dropdown(['全部图片','未生成','生成失败','已完成但无标签',*tag_names],value='全部图片',label='检查范围')
                diagnostic_refresh = gr.Button('刷新检查')
                diagnostic_summary = gr.Textbox(label='覆盖情况',interactive=False)
                counts = gr.Dataframe(headers=['类别','有标签图片数','可搜索图片数'],interactive=False)
                details = gr.Dataframe(headers=['文件名','描述状态','实际标签','可搜索','描述','错误'],interactive=False)
                diagnostic_gallery = gr.Gallery(label='检查素材（选中后到素材工作台查看详情）',columns=5,type='filepath',allow_preview=False)
                diagnostic_refs = gr.State([])
                batch = gr.Button('补齐全库未生成 / 失败图片标签')
                gr.Markdown('处理全库，不受检查范围限制；已完成项跳过。每张需要加载模型并推理，可能耗时较长。')
                batch_status = gr.Textbox(label='批量任务进度',interactive=False)

        inputs = [query,kind,tag,keyword,limit]
        outputs = [gallery,refs,summary]
        diagnostic_outputs = [diagnostic_summary,counts,details,diagnostic_gallery,diagnostic_refs]
        selection = [detail,download,player,selected,frames,frame_refs,preview,description]
        for event in (search.click,query.submit,kind.change,tag.change,keyword.submit,limit.release,refresh.click):
            event(browse,inputs,outputs)
        clear.click(lambda: '', outputs=query).then(browse,inputs,outputs)
        upload.click(upload_files,files,import_report).then(browse,inputs,outputs).then(callbacks['inspect_tags'],category,diagnostic_outputs)
        gallery.select(callbacks['select'],refs,selection)
        frames.select(callbacks['select'],frame_refs,selection)
        diagnostic_gallery.select(callbacks['select'],diagnostic_refs,selection)
        for button, fn, ins, outs in [(describe,callbacks['describe_video'],selected,description),(index,index_all,None,task),(retry,retry_one,selected,task),(warmup,callbacks['warmup'],None,task),(batch,callbacks['complete_tags'],category,[batch_status,*diagnostic_outputs])]:
            button.click(lambda: gr.update(interactive=False),outputs=button,queue=False).then(fn,ins,outs,concurrency_id='model-task',concurrency_limit=1).then(lambda: gr.update(interactive=True),outputs=button).then(browse,inputs,outputs).then(callbacks['inspect_tags'],category,diagnostic_outputs)
        category.change(callbacks['inspect_tags'],category,diagnostic_outputs)
        diagnostic_refresh.click(callbacks['inspect_tags'],category,diagnostic_outputs)
        page.load(browse,inputs,outputs)
        page.load(callbacks['inspect_tags'],category,diagnostic_outputs)
    page.objectlift_callbacks = {**callbacks, 'browse': browse}
    return page
