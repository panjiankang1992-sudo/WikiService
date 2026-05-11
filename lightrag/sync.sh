#!/bin/bash
cd /opt/mycode/WikiService/lightrag
mkdir -p templates

cat > templates/index.html << 'HTMLEND'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WikiService 知识库</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        header h1 { font-size: 2rem; margin-bottom: 5px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #667eea; font-size: 2rem; margin-bottom: 5px; }
        .main-content { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 768px) { .main-content { grid-template-columns: 1fr; } }
        .panel { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .panel h2 { color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #667eea; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #555; font-weight: 500; }
        textarea, input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        textarea { resize: vertical; min-height: 100px; }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { transform: translateY(-2px); }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .answer { margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; border-left: 4px solid #667eea; line-height: 1.6; white-space: pre-wrap; }
        .error { background: #fee; color: #c00; padding: 10px; border-radius: 5px; margin-top: 10px; }
        .success { background: #efe; color: #060; padding: 10px; border-radius: 5px; margin-top: 10px; }
        .spinner { display: inline-block; width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .file-upload { border: 2px dashed #ddd; padding: 20px; text-align: center; border-radius: 5px; margin-bottom: 15px; cursor: pointer; }
        .file-upload:hover { border-color: #667eea; }
        .file-upload input { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>WikiService 知识库</h1>
            <p>基于 LightRAG + DeepSeek 的智能问答系统</p>
        </header>
        <div class="stats" id="stats">
            <div class="stat-card"><h3 id="chunks">-</h3><p>文本块</p></div>
            <div class="stat-card"><h3 id="entities">-</h3><p>实体</p></div>
            <div class="stat-card"><h3 id="relations">-</h3><p>关系</p></div>
        </div>
        <div class="main-content">
            <div class="panel">
                <h2>添加知识</h2>
                <div class="form-group">
                    <label>上传文件</label>
                    <div class="file-upload" onclick="document.getElementById('file-input').click()">
                        <input type="file" id="file-input">
                        <p>点击选择文件 (.txt, .md)</p>
                        <p id="file-name" style="font-weight:bold; margin-top:10px;"></p>
                    </div>
                </div>
                <div class="form-group">
                    <label>或直接输入文本</label>
                    <textarea id="text-input" placeholder="在此输入要添加的知识内容..."></textarea>
                </div>
                <button id="ingest-btn" onclick="ingest()">添加到知识库</button>
                <div id="ingest-result"></div>
            </div>
            <div class="panel">
                <h2>智能问答</h2>
                <div class="form-group">
                    <label>选择检索模式</label>
                    <select id="mode-select">
                        <option value="hybrid">混合模式 (推荐)</option>
                        <option value="naive">朴素模式</option>
                        <option value="local">局部模式</option>
                        <option value="global">全局模式</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>输入问题</label>
                    <textarea id="question-input" placeholder="请输入您的问题..."></textarea>
                </div>
                <button id="query-btn" onclick="query()">查询</button>
                <div id="query-result"></div>
            </div>
        </div>
        <div style="margin-top:20px; text-align:center;">
            <button onclick="clearAll()" style="background:#dc3545; width:auto;">清空知识库</button>
        </div>
    </div>
    <script>
        document.getElementById("file-input").addEventListener("change", function(e) {
            var file = e.target.files[0];
            if (file) document.getElementById("file-name").textContent = file.name;
        });
        function loadStats() {
            fetch("/api/stats").then(r=>r.json()).then(d=>{
                document.getElementById("chunks").textContent = d.chunks_count || 0;
                document.getElementById("entities").textContent = d.entities_count || 0;
                document.getElementById("relations").textContent = d.relations_count || 0;
            });
        }
        function ingest() {
            var file = document.getElementById("file-input").files[0];
            var text = document.getElementById("text-input").value.trim();
            var btn = document.getElementById("ingest-btn");
            var result = document.getElementById("ingest-result");
            if (!file && !text) { result.innerHTML = '<div class="error">请选择文件或输入文本</div>'; return; }
            btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>处理中...'; result.innerHTML = '';
            if (file) {
                var formData = new FormData(); formData.append("file", file);
                fetch("/api/ingest/file", {method:"POST", body:formData}).then(r=>r.json()).then(d=>{
                    if (d.error) result.innerHTML = '<div class="error">'+d.error+'</div>';
                    else { result.innerHTML = '<div class="success">成功: '+d.filename+'</div>'; document.getElementById("text-input").value=""; loadStats(); }
                }).catch(e=>result.innerHTML='<div class="error">'+e.message+'</div>').finally(()=>{btn.disabled=false; btn.innerHTML="添加到知识库";});
            } else {
                fetch("/api/ingest", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text:text})}).then(r=>r.json()).then(d=>{
                    if (d.error) result.innerHTML = '<div class="error">'+d.error+'</div>';
                    else { result.innerHTML = '<div class="success">成功添加</div>'; document.getElementById("text-input").value=""; loadStats(); }
                }).catch(e=>result.innerHTML='<div class="error">'+e.message+'</div>').finally(()=>{btn.disabled=false; btn.innerHTML="添加到知识库";});
            }
        }
        function query() {
            var question = document.getElementById("question-input").value.trim();
            var mode = document.getElementById("mode-select").value;
            var btn = document.getElementById("query-btn");
            var result = document.getElementById("query-result");
            if (!question) { result.innerHTML = '<div class="error">请输入问题</div>'; return; }
            btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>思考中...';
            fetch("/api/query", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({question:question, mode:mode})}).then(r=>r.json()).then(d=>{
                if (d.error) result.innerHTML = '<div class="error">'+d.error+'</div>';
                else result.innerHTML = '<div class="answer">'+d.answer+'</div>';
            }).catch(e=>result.innerHTML='<div class="error">'+e.message+'</div>').finally(()=>{btn.disabled=false; btn.innerHTML="查询";});
        }
        function clearAll() {
            if (!confirm("确定清空知识库？")) return;
            fetch("/api/clear", {method:"POST"}).then(r=>r.json()).then(d=>{ if(d.success){alert("已清空");loadStats();} });
        }
        loadStats();
    </script>
</body>
</html>
HTMLEND

echo "HTML template created"
