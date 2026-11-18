import hashlib
import fcntl
import io
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import analyze, effective_selected
from .models import Decision, ImportManifest, PresetInput, Receipt, Revision, SettingsUpdate
from .store import Store

MAX_PREVIEW_BYTES = 24 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 50_000_000

def criteria_for(settings):
    result = [{'text': x, 'status': 'partial', 'reason': 'Copertura prudente: mantenimento delle immagini non equivalenti; nessuna comprensione di scene o persone nel motore iniziale.'}
              for x in settings.get('preset_snapshot', {}).get('criteria', [])]
    if settings.get('instructions', '').strip():
        result.append({'text': settings['instructions'], 'status': 'unsupported',
                       'reason': 'Istruzione salvata per la revisione manuale; il motore iniziale non interpreta testo libero.'})
    return result

def load_connection_token(root: Path):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_file = root / 'connection-token'
    if not token_file.exists():
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_urlsafe(32))
    return token_file.read_text().strip()

def create_app(data_dir: Path | None = None, token: str | None = None, web_dir: Path | None = None):
    root = data_dir or Path(os.environ.get('LRC_SELECTION_DATA', Path.home() / 'Library/Application Support/LrC Photo Selection'))
    store = Store(root)
    if token is None:
        token = load_connection_token(root)
    if not token:
        raise ValueError('Connection token must not be empty')
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='selection')

    @asynccontextmanager
    async def lifespan(app):
        lock_file = (root / 'server.lock').open('a')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            raise RuntimeError('Un backend usa già questa directory dati')
        try:
            store.recover_jobs()
            yield
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    app = FastAPI(title='LrC Photo Selection', version='0.1.0', lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def protect(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return Response('Origine non consentita', status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return Response('Richiesta cross-site non consentita', status_code=403)
        if request.url.path.startswith('/api/') and request.url.path != '/api/session':
            supplied = request.headers.get('authorization', '').removeprefix('Bearer ') or request.cookies.get('lrc_session', '')
            if not secrets.compare_digest(supplied, token):
                return Response('Connessione non autenticata', status_code=401)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
        return response

    class SessionInput(BaseModel):
        token: str

    @app.post('/api/session')
    def session(body: SessionInput, response: Response):
        if not secrets.compare_digest(body.token, token):
            raise HTTPException(401, 'Token non valido')
        response.set_cookie('lrc_session', token, httponly=True, samesite='strict', path='/')
        return {'ok': True}

    @app.get('/health')
    def health():
        return {'status': 'ok', 'version': '0.1.0'}

    @app.get('/api/presets')
    def presets():
        with store.connect() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM presets')]

    @app.post('/api/presets')
    def create_preset(body: PresetInput):
        preset = {'id': str(uuid.uuid4()), 'name': body.name, 'criteria': body.criteria, 'version': 1}
        with store.transaction() as db:
            db.execute('INSERT INTO presets VALUES(?,?)', (preset['id'], json.dumps(preset)))
        return preset

    @app.put('/api/presets/{pid}')
    def update_preset(pid: str, body: PresetInput):
        with store.transaction() as db:
            row = db.execute('SELECT body FROM presets WHERE id=?', (pid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Preset non trovato')
            old = json.loads(row['body'])
            if old['version'] != body.version:
                raise HTTPException(409, 'Preset modificato: ricaricare')
            updated = {'id': pid, 'name': body.name, 'criteria': body.criteria, 'version': old['version'] + 1}
            db.execute('UPDATE presets SET body=? WHERE id=?', (json.dumps(updated), pid))
        return updated

    @app.post('/api/imports')
    def import_service(body: ImportManifest):
        digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with store.transaction() as db:
            existing = db.execute('SELECT body FROM services WHERE id=?', (body.id,)).fetchone()
            if existing:
                service = json.loads(existing['body'])
                if service['manifest_sha256'] != digest:
                    raise HTTPException(409, 'ID servizio già usato da un manifest differente')
                return service
            preset = json.loads(db.execute("SELECT body FROM presets WHERE id='wedding'").fetchone()['body'])
            settings = {'target': min(500, len(body.photos)), 'preset_id': preset['id'], 'preset_version': preset['version'],
                        'preset_snapshot': preset, 'mode': 'local', 'instructions': '', 'camera_offsets': {}}
            service = {'id': body.id, 'title': body.title, 'catalog_id': body.catalog_id, 'catalog_label': body.catalog_label,
                       'schema_version': 1, 'manifest_sha256': digest, 'revision': 1, 'status': 'importing',
                       'settings': settings, 'photos': [dict(p.model_dump(), preview_ready=False) for p in body.photos],
                       'decisions': {}, 'proposal': None, 'job': None, 'receipts': [], 'criteria': criteria_for(settings)}
            store.put(db, service)
        return service

    @app.get('/api/services')
    def services():
        with store.connect() as db:
            items = [json.loads(r['body']) for r in db.execute('SELECT body FROM services ORDER BY rowid DESC')]
        return [{k: s[k] for k in ['id', 'title', 'catalog_id', 'revision', 'status']} | {'photo_count': len(s['photos'])} for s in items]

    @app.get('/api/services/{sid}')
    def detail(sid: str):
        service = store.get(sid)
        service['selected_ids'] = effective_selected(service)
        return service

    @app.put('/api/services/{sid}/photos/{pid}/preview')
    async def upload_preview(sid: str, pid: str, request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_PREVIEW_BYTES:
                raise HTTPException(413, 'Anteprima troppo grande')
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.format != 'JPEG':
                    raise ValueError('Formato diverso da JPEG')
                im.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, 'Anteprima JPEG non valida')
        digest = hashlib.sha256(data).hexdigest()
        with store.transaction() as db:
            service = store.get(sid, db)
            photo = next((p for p in service['photos'] if p['id'] == pid), None)
            if photo is None:
                raise HTTPException(404, 'Foto non trovata')
            if photo.get('preview_sha256') == digest:
                return {'ok': True}
            if service['status'] != 'importing':
                raise HTTPException(409, 'Importazione chiusa: creare un nuovo servizio per anteprime differenti')
            path = store.preview_path(sid, pid)
            if shutil.disk_usage(store.root).free < len(data) + 512 * 1024 * 1024:
                raise HTTPException(507, 'Spazio insufficiente: importazione sospesa, dati già ricevuti conservati')
            path.parent.mkdir(exist_ok=True, mode=0o700)
            temporary = path.with_suffix('.tmp')
            temporary.write_bytes(data)
            temporary.chmod(0o600)
            temporary.replace(path)
            photo.update(preview_ready=True, preview_sha256=digest)
            service['revision'] += 1
            store.put(db, service)
        return {'ok': True}

    @app.get('/api/services/{sid}/photos/{pid}/preview')
    def preview(sid: str, pid: str):
        s = store.get(sid)
        if not any(p['id'] == pid and p['preview_ready'] for p in s['photos']):
            raise HTTPException(404, 'Anteprima non disponibile')
        return FileResponse(store.preview_path(sid, pid), media_type='image/jpeg')

    @app.post('/api/services/{sid}/complete')
    def complete(sid: str):
        with store.transaction() as db:
            s = store.get(sid, db)
            if s['status'] == 'importing':
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)
        return s

    def require_editable(service):
        if service['status'] == 'applying':
            raise HTTPException(409, 'Applicazione stelle in corso: completare o riprendere dal plugin.')

    @app.put('/api/services/{sid}/settings')
    def settings(sid: str, body: SettingsUpdate):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            if body.settings.target > len(s['photos']):
                raise HTTPException(422, 'Quantità superiore alle foto importate')
            new = body.settings.model_dump()
            if (new['preset_id'], new['preset_version']) == (s['settings']['preset_id'], s['settings']['preset_version']):
                new['preset_snapshot'] = s['settings']['preset_snapshot']
            else:
                row = db.execute('SELECT body FROM presets WHERE id=?', (new['preset_id'],)).fetchone()
                if not row or json.loads(row['body'])['version'] != new['preset_version']:
                    raise HTTPException(409, 'Versione preset non disponibile: ricaricare')
                new['preset_snapshot'] = json.loads(row['body'])
            s['settings'] = new
            s['criteria'] = criteria_for(new)
            s['revision'] += 1
            if s.get('proposal'):
                s['proposal']['stale'] = True
                s['proposal']['warnings'].append('Impostazioni cambiate: avviare una nuova analisi per aggiornare la proposta.')
            store.put(db, s)
        return s

    @app.patch('/api/services/{sid}/decisions/{pid}')
    def decide(sid: str, pid: str, body: Decision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            if not any(p['id'] == pid for p in s['photos']):
                raise HTTPException(404, 'Foto non trovata')
            selected = set(effective_selected(s)) - {pid}
            if body.state in ('excluded', 'alternative') and not body.confirm_last:
                groups = s['proposal']['groups'] if s['proposal'] else [{'members': [pid]}]
                if any(pid in g['members'] and not selected.intersection(g['members']) for g in groups):
                    raise HTTPException(409, {'code': 'last_candidate', 'message': 'Escludi l’ultima candidata del gruppo. Confermare?'})
            s['decisions'][pid] = {'state': body.state, 'locked': body.locked}
            s['revision'] += 1
            store.put(db, s)
        return s

    def run_analysis(sid: str, start_revision: int):
        try:
            snapshot = store.get(sid)
            proposal = analyze(snapshot)
            with store.transaction() as db:
                s = store.get(sid, db)
                if s['revision'] != start_revision:
                    s['job'] = {'status': 'interrupted', 'completed': 0, 'total': len(s['photos']), 'error': 'Decisioni o impostazioni cambiate durante l’analisi; riavviare.'}
                else:
                    s['proposal'] = proposal
                    s['job'] = {'status': 'completed', 'completed': len(s['photos']), 'total': len(s['photos']), 'error': None}
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)
        except Exception:
            with store.transaction() as db:
                s = store.get(sid, db)
                s['job'] = {'status': 'failed', 'completed': 0, 'total': len(s['photos']), 'error': 'Analisi non riuscita. Dati e decisioni conservati.'}
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)

    @app.post('/api/services/{sid}/analyze')
    def start_analysis(sid: str, body: Revision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            if s['status'] != 'ready':
                raise HTTPException(409, 'Servizio non pronto o analisi già in corso')
            if s['settings']['mode'] != 'local':
                raise HTTPException(409, 'Modalità ibrida non abilitata: occorrono campione, modello e budget autorizzati.')
            s['status'] = 'analyzing'
            s['job'] = {'status': 'running', 'completed': 0, 'total': len(s['photos']), 'error': None}
            s['revision'] += 1
            store.put(db, s)
        executor.submit(run_analysis, sid, s['revision'])
        return s

    @app.post('/api/services/{sid}/rating-plan')
    def rating_plan(sid: str, body: Revision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            if s['status'] != 'ready':
                raise HTTPException(409, 'Completare importazione/analisi prima di preparare le stelle')
            if s.get('proposal') and s['proposal'].get('stale'):
                raise HTTPException(409, 'Proposta obsoleta: avviare nuovamente la selezione prima delle stelle')
            # Applied, conflicting and uncertain attempts are protected. Never-started skips may retry.
            attempted = {r['photo_id'] for receipt in s['receipts'] for r in receipt['results'] if r['status'] != 'skipped'}
            selected = set(effective_selected(s))
            items, warnings = [], []
            for p in s['photos']:
                if p['id'] not in selected or p['baseline_rating'] != 0 or p['id'] in attempted:
                    continue
                if p['baseline_edit_time'] is None:
                    warnings.append(f"{p['filename']}: stato iniziale non verificabile, nessuna stella applicabile")
                    continue
                items.append({'photo_id': p['id'], 'uuid': p['uuid'], 'local_id': p['local_id'], 'expected_rating': 0,
                              'expected_edit_time': p['baseline_edit_time'], 'target_rating': 1})
            plan = {'batch_id': str(uuid.uuid4()), 'service_id': sid, 'catalog_id': s['catalog_id'], 'revision': s['revision'],
                    'items': items, 'warnings': warnings, 'created_at': time.time(), 'schema_version': 1}
            db.execute('INSERT INTO batches VALUES(?,?,?)', (plan['batch_id'], sid, json.dumps(plan)))
        return plan

    @app.get('/api/services/{sid}/rating-plan/latest')
    def latest_plan(sid: str):
        with store.connect() as db:
            s = store.get(sid, db)
            row = db.execute('SELECT body FROM batches WHERE service_id=? ORDER BY rowid DESC LIMIT 1', (sid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Preparare prima le stelle dalla web app')
            plan = json.loads(row['body'])
            store.check_revision(s, plan['revision'])
            return plan

    class ClaimInput(BaseModel):
        batch_id: str

    @app.post('/api/services/{sid}/rating-plan/claim')
    def claim_plan(sid: str, body: ClaimInput):
        with store.transaction() as db:
            s = store.get(sid, db)
            row = db.execute('SELECT body FROM batches WHERE id=? AND service_id=?', (body.batch_id, sid)).fetchone()
            if not row:
                raise HTTPException(404, 'Piano non trovato')
            plan = json.loads(row['body'])
            store.check_revision(s, plan['revision'])
            if s['status'] == 'applying' and s.get('active_batch_id') == body.batch_id:
                return {'ok': True, 'resumed': True}
            if s['status'] != 'ready':
                raise HTTPException(409, 'Servizio occupato')
            s['status'] = 'applying'
            s['active_batch_id'] = body.batch_id
            store.put(db, s)
        return {'ok': True, 'resumed': False}

    @app.post('/api/services/{sid}/rating-receipts')
    def receipt(sid: str, body: Receipt):
        with store.transaction() as db:
            s = store.get(sid, db)
            row = db.execute('SELECT body FROM batches WHERE id=? AND service_id=?', (body.batch_id, sid)).fetchone()
            if not row:
                raise HTTPException(404, 'Applicazione non trovata')
            plan = json.loads(row['body'])
            allowed = {i['photo_id'] for i in plan['items']}
            if len({r.photo_id for r in body.results}) != len(body.results) or any(r.photo_id not in allowed for r in body.results):
                raise HTTPException(422, 'Ricevuta non corrispondente al piano')
            incoming = body.model_dump()
            old = next((r for r in s['receipts'] if r['batch_id'] == body.batch_id), None)
            if old:
                if old != incoming:
                    raise HTTPException(409, 'Ricevuta già registrata con esiti differenti')
                return {'ok': True}
            if s.get('active_batch_id') != body.batch_id:
                raise HTTPException(409, 'Il piano deve essere acquisito dal plugin prima della ricevuta')
            if {r.photo_id for r in body.results} != allowed:
                raise HTTPException(422, 'La ricevuta deve riportare un esito per ogni foto del piano')
            if any(r.status == 'applied' and (r.before != 0 or r.after != 1) for r in body.results):
                raise HTTPException(422, 'Esito applicato non valido: ammesse solo stelle da 0 a 1')
            s['receipts'].append(incoming)
            s['status'] = 'ready'
            s.pop('active_batch_id', None)
            s['revision'] += 1
            store.put(db, s)
        return {'ok': True}

    assets = web_dir or Path(__file__).resolve().parents[2] / 'web/dist'
    if assets.is_dir():
        app.mount('/', StaticFiles(directory=assets, html=True), name='web')
    else:
        @app.get('/')
        def no_build():
            return {'message': 'Frontend non compilato. Eseguire npm ci e npm run build nella cartella web.'}
    return app
