import yt_dlp
import os
import nodejs
import time
import socket
import imageio_ffmpeg

def is_connected():
    try:
        # Încercăm să conectăm la cel mai rapid și stabil server DNS comun (Cloudflare/Google)
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        return True
    except OSError:
        pass
    return False

def get_all_urls(input_urls):
    """Extrage toate link-urile individuale (din link-uri simple sau playlist-uri)."""
    all_video_urls = []
    # Opțiuni minimale doar pentru extragere rapidă
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'remote_components': ['ejs:github'],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }
    
    print("🔍 Se analizează link-urile și playlist-urile...")
    
    # Căutăm fișierul de cookie-uri în folderul scriptului
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_cookies = ["cookies.txt", "www.youtube.com_cookies.txt"]
    found_cookie = next((os.path.join(script_dir, f) for f in possible_cookies if os.path.exists(os.path.join(script_dir, f))), None)

    # Încercăm pe rând mai multe metode de autentificare
    browsers = ['chrome', 'edge', 'firefox']
    if found_cookie:
        ydl_opts['cookiefile'] = found_cookie
        browsers = [None] # Folosim doar fișierul dacă există
        print(f"🍪 Se folosește fișierul de cookie-uri: {os.path.basename(found_cookie)}")

    for browser in browsers:
        if browser: ydl_opts['cookiesfrombrowser'] = (browser,)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for url in input_urls:
                    try:
                        if not is_connected():
                            print("📡 Se așteaptă internetul pentru scanare...")
                            while not is_connected(): time.sleep(5)
                        
                        info = ydl.extract_info(url, download=False)
                        if 'entries' in info:
                            entries = list(info['entries'])
                            print(f"📂 Playlist detectat: {info.get('title', 'Nume necunoscut')} ({len(entries)} clipuri)")
                            for entry in entries:
                                if entry and 'url' in entry:
                                    all_video_urls.append(entry['url'])
                        else:
                            all_video_urls.append(url)
                    except Exception as e:
                        if "confirm you're not a bot" in str(e).lower() or "cookie" in str(e).lower():
                            raise e # Forțăm trecerea la următorul browser
                        print(f"⚠️ Nu am putut citi link-ul {url}: {e}")
                return all_video_urls # Dacă am ajuns aici, am terminat cu succes
        except Exception as e:
            if browser: print(f"ℹ️ {browser.capitalize()} e blocat sau nu are cookie-uri. Încercăm următorul...")
            continue
            
    return all_video_urls

def download_videos(urls, output_path=r"C:\DEPOZIT\YOUTUBE\History memes\Prod"):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        
    # 1. Încercăm să adăugăm Deno în PATH (motorul de JS recomandat)
    deno_path = os.path.expanduser("~\\.deno\\bin")
    if os.path.exists(deno_path):
        os.environ["PATH"] = deno_path + os.pathsep + os.environ["PATH"]
    
    # 2. Încercăm să adăugăm Node.js din Python (ca fallback)
    try:
        import nodejs
        os.environ["PATH"] = os.path.dirname(nodejs.node.path) + os.pathsep + os.environ["PATH"]
    except Exception:
        pass
        
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    # Prima dată "aplatizăm" lista de link-uri (expandăm playlist-urile)
    final_urls = get_all_urls(urls)
    total = len(final_urls)
    
    if total == 0:
        print("❌ Nu am găsit niciun videoclip de descărcat.")
        return

    print(f"🚀 Începe descărcarea a {total} videoclipuri...\n")

    for idx, url in enumerate(final_urls, start=1):
        video_folder = os.path.join(output_path, str(idx))
        
        # Verificăm dacă videoclipul a fost deja descărcat cu succes în acest folder
        if os.path.exists(video_folder):
            existing_mp4 = [f for f in os.listdir(video_folder) if f.endswith('.mp4')]
            if existing_mp4:
                print(f"⏭️ [{idx}/{total}] Skip: Videoclipul există deja în folderul '{idx}'.")
                continue

        if not os.path.exists(video_folder):
            os.makedirs(video_folder)

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(video_folder, f'%(title)s.%(ext)s'), 
            'noplaylist': True, # Deja am extras din playlist, acum descărcăm clipul individual
            'merge_output_format': 'mp4',
            'ffmpeg_location': ffmpeg_path,
            'remote_components': ['ejs:github'],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            # Parametri de stabilitate pentru rețele slabe/VPN:
            'retries': 20,
            'fragment_retries': 20,
            'retry_sleep_functions': {'http': lambda n: 5},
            'continuedl': True, # Permite reluarea unui fragment început
        }
        
        # Încercăm autentificarea pentru download
        download_success = False
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_cookies = ["cookies.txt", "www.youtube.com_cookies.txt"]
        found_cookie = next((os.path.join(script_dir, f) for f in possible_cookies if os.path.exists(os.path.join(script_dir, f))), None)
        
        browsers = ['chrome', 'edge', 'firefox']
        if found_cookie:
            ydl_opts['cookiefile'] = found_cookie
            browsers = [None]

        for browser in browsers:
            if browser: ydl_opts['cookiesfrombrowser'] = (browser,)
            
            while True:
                try:
                    if not is_connected():
                        print(f"\n📡 [Clip {idx}/{total}] Conexiune pierdută. Aștept internetul...")
                        while not is_connected(): time.sleep(10)

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        print(f"\n📥 [{idx}/{total}] Descărcare în folderul '{idx}' (via {browser if browser else 'cookies.txt'}): {url}")
                        ydl.download([url])
                        print(f"✅ Videoclipul {idx} s-a descărcat cu succes!")
                        download_success = True
                        break 
                        
                except Exception as e:
                    error_str = str(e).lower()
                    if "confirm you're not a bot" in error_str and browser != browsers[-1]:
                        print(f"ℹ️ {browser.capitalize()} a eșuat la bot-check. Încercăm browser-ul următor...")
                        break # Ieșim din while True pentru acest browser, mergem la următorul

                    network_errors = ["connection", "timeout", "unreachable", "10054", "reset", "bytes read", "expected", "eof"]
                    if any(x in error_str for x in network_errors):
                        print(f"\n⚠️ Eroare de rețea détectată ({idx}/{total}). Reîncercare automată în 10 secunde...")
                        time.sleep(10)
                    elif any(x in error_str for x in ["unavailable", "private", "not found"]):
                        print(f"\n❌ Clipul {idx} e indisponibil/privat. Salt...")
                        download_success = True # Considerăm "gata" pentru a trece la următorul URL
                        break
                    else:
                        print(f"\n❌ Eroare fatală la clipul {idx}: {e}")
                        download_success = True 
                        break
            if download_success: break # Am terminat cu acest URL, trecem la următorul din lista mare (enumerate)

if __name__ == "__main__":
    print("=== YouTube Downloader (Multi & Playlist Support) ===")
    
    while True:
        try:
            user_input = input("\nIntrodu Link (Video/Playlist) SAU calea către un fișier .txt: ")
            if not user_input.strip(): continue
                
            input_val = user_input.strip().replace('"', '')
                
            if os.path.isfile(input_val):
                with open(input_val, 'r', encoding='utf-8') as f:
                    urls = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
                if urls: download_videos(urls)
                else: print("Fișier gol.")
            else:
                download_videos([input_val])
                
        except KeyboardInterrupt:
            print("\nLa revedere!")
            break

