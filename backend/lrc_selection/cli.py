import argparse
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='LrC Photo Selection — solo locale')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/LrC Photo Selection')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--show-connection', action='store_true', help='Mostra il token locale per configurare il plugin; non è una chiave API')
    args = parser.parse_args()
    os.umask(0o077)
    from .app import create_app, load_connection_token
    if args.show_connection:
        print('Token di connessione locale (non condividere):')
        print(load_connection_token(args.data_dir))
        return
    app = create_app(args.data_dir)
    import uvicorn
    print(f'Apri http://127.0.0.1:{args.port} — nessun catalogo viene aperto automaticamente.')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)

if __name__ == '__main__':
    main()
