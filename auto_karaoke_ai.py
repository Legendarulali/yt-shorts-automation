import os
import json
import time
import warnings
import numpy as np
from concurrent.futures import ProcessPoolExecutor

# Dezactivăm avertismentele sâcâitoare de citire a ultimului cadru din MoviePy/FFmpeg
warnings.filterwarnings("ignore", category=UserWarning, message=".*bytes wanted but 0 bytes read.*")

# Suprimăm avertismentele Hugging Face despre Symlinks pe Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from faster_whisper import WhisperModel
from moviepy import VideoFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoClip
import render_utils

# -= Configurare Layout =-
CANVAS_W = 1080
CANVAS_H = 1920
VIDEO_Y = 400
SUBS_Y_BASE = 1400

# Dicționar pentru corecții automate
AUTOCORRECT = {
    "lol" : "Lowell",
    "dominos": "DOOMinos",
    "youtube": "YouTube",
    "shorts": "Shorts"
}

def apply_autocorrect(text):
    words = text.split()
    new_words = [AUTOCORRECT.get(w.lower().strip(".,!?"), w) for w in words]
    return " ".join(new_words)

def split_into_smart_chunks(segments):
    """
    Împarte segmentele Whisper în bucăți mici (2-4 cuvinte) adaptate stilului Shorts.
    Reguli:
    - Max 4 cuvinte pe grup.
    - Break la cuvinte lungi (>10 caractere) pentru a fi singure pe rând.
    - Break la detectarea speaker-ului (simbolul :).
    """
    smart_chunks = []
    
    for seg in segments:
        words = seg.get('words', [])
        if not words: continue
        
        current_group = []
        for w in words:
            word_text = w['word'].strip()
            
            # Condiții de split
            is_too_long = len(word_text) > 10
            is_speaker = ":" in word_text
            
            # Dacă grupul e plin SAU cuvântul e special, salvăm ce avem
            if len(current_group) >= 4 or is_too_long or is_speaker:
                if current_group:
                    smart_chunks.append({
                        'start': current_group[0]['start'],
                        'end': current_group[-1]['end'],
                        'words': current_group
                    })
                    current_group = []
            
            current_group.append(w)
            
            # Dacă am adăugat un cuvânt "special", închidem imediat grupul ca să rămână singur
            if is_too_long or is_speaker:
                smart_chunks.append({
                    'start': current_group[0]['start'],
                    'end': current_group[-1]['end'],
                    'words': current_group
                })
                current_group = []
                
        # Adăugăm restul
        if current_group:
            smart_chunks.append({
                'start': current_group[0]['start'],
                'end': current_group[-1]['end'],
                'words': current_group
            })
            
    return smart_chunks

def transcribe_video(model, video_path, json_path):
    """Pasul 1: Transcrierea video-ului și generarea fișierului JSON."""
    print(f"🎤 [Faster-Whisper] Analizez: {os.path.basename(video_path)}...")
    
    # beam_size=5 oferă un echilibru bun între viteză și acuratețe
    # word_timestamps=True este necesar pentru karaoke
    segments_gen, info = model.transcribe(video_path, beam_size=5, word_timestamps=True)
    
    segments = []
    for seg in segments_gen:
        words = []
        if seg.words:
            for w in seg.words:
                clean_word = apply_autocorrect(w.word.strip())
                words.append({
                    "word": clean_word,
                    "start": w.start,
                    "end": w.end
                })
        
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "words": words
        })
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=4, ensure_ascii=False)
    
    print(f"✅ JSON salvat: {os.path.basename(json_path)}")

def render_short(video_path, json_path, output_path):
    """Pasul 2: Randarea Master-ului (Fundal Blurat + Karaoke)."""
    print(f"🎬 [Stage 1] Generez Master cu Blur: {os.path.basename(video_path)}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_segments = json.load(f)
        
    # Aplicăm transformarea în mini-segmente (max 4 cuvinte)
    segments = split_into_smart_chunks(raw_segments)
    
    video = VideoFileClip(video_path)
    
    # --- LOGICĂ FUNDAL MINIMAL (ALB CURAT) ---
    # Baza: Alb solid (1080x1920) - Foarte rapid de randat
    bg_white = ColorClip(size=(CANVAS_W, CANVAS_H), color=(255, 255, 255)).with_duration(video.duration)
    
    # --- LOGICĂ VIDEO CENTRAL ---
    # Poziționăm video-ul principal la lățimea 1080, centrat pe Y
    video_main = video.resized(width=CANVAS_W)
    scaled_h = video_main.size[1]
    # Centrare pe verticală (Canvas e 1920, Video e scaled_h)
    video_y_centered = (CANVAS_H - scaled_h) // 2
    video_final = video_main.with_position((0, video_y_centered))
    
    # --- LOGICĂ SUBTITRĂRI UNIFICATE (MASTER STREAM) ---
    # Întreaga logică de karaoke acum într-un singur flux continuu
    # Folosim cache persistent pe toată durata clipului
    stream_cache = {
        'last_t': -1,
        'last_seg_idx': 0,
        'last_active_word_idx': -2,
        'img': None,
        'mask': None
    }
    
    def make_subs_frame(t, cache=stream_cache):
        # 1. Găsim segmentul curent (accelerat - căutăm pornind de la ultimul index cunoscut)
        current_seg = None
        for i in range(cache['last_seg_idx'], len(segments)):
            seg = segments[i]
            if seg['start'] <= t <= seg['end']:
                cache['last_seg_idx'] = i
                current_seg = seg
                break
            if seg['start'] > t: # Am depășit timpul, nu mai căutăm
                break
        
        if not current_seg:
            # Nu e nimic de desenat acum
            cache['img'] = np.zeros((CANVAS_H, CANVAS_W, 3), dtype='uint8')
            cache['mask'] = np.zeros((CANVAS_H, CANVAS_W), dtype='float32')
            cache['last_active_word_idx'] = -2
            return cache['img']
            
        # 2. Găsim cuvântul activ în cadrul segmentului
        active_idx = -1
        for i, w in enumerate(current_seg['words']):
            if w['start'] <= t <= w['end']:
                active_idx = i
                break
        
        # 3. Cache Match? (Dacă e același cuvânt activ în același segment, returnăm din RAM)
        if active_idx == cache['last_active_word_idx'] and cache['img'] is not None:
            return cache['img']
            
        # 4. Desenăm (doar dacă e necesar)
        img_pil = render_utils.generate_karaoke_frame(CANVAS_W, CANVAS_H, current_seg, t, font_size=75)
        cache['img'] = np.array(img_pil)[:, :, :3]
        cache['mask'] = np.array(img_pil)[:, :, 3] / 255.0
        cache['last_active_word_idx'] = active_idx
        return cache['img']

    def make_subs_mask(t, cache=stream_cache):
        # Masca e calculată deja în make_subs_frame
        if cache['mask'] is not None:
            return cache['mask']
        return np.zeros((CANVAS_H, CANVAS_W))

    # Un singur clip de subtitrare pentru tot videoclipul
    subs_stream = VideoClip(make_subs_frame, duration=video.duration).with_mask(
        VideoClip(make_subs_mask, is_mask=True, duration=video.duration)
    )

    # Compoziția finală (Alb solid -> Video Main -> Subtitrări)
    # Am eliminat complet video-ul blurat pentru viteză maximă și aspect curat
    result = CompositeVideoClip([bg_white, video_final, subs_stream])
    
    # Export Turbo AMF
    result.write_videofile(
        output_path, 
        fps=30, 
        codec="h264_amf", 
        audio_codec="aac", 
        temp_audiofile="temp-audio.m4a", 
        remove_temp=True,
        threads=os.cpu_count(),
        preset="balanced",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    video.close()
    result.close()

def render_folder_task(folder):
    """Sarcina de randare pentru un singur folder (folosită pentru procesare în paralel)."""
    mp4_files = [f for f in os.listdir(folder) if f.lower().endswith('.mp4') and not f.startswith('FINAL_')]
    if not mp4_files: 
        return f"⏭️ {os.path.basename(folder)}: Nu există .mp4"
    
    video_path = os.path.join(folder, mp4_files[0])
    json_path = os.path.join(folder, "transcript.json")
    output_path = os.path.join(folder, f"FINAL_SHORT_{os.path.basename(folder)}.mp4")
    
    if os.path.exists(output_path):
        return f"⏭️ Skip: {os.path.basename(output_path)} există deja."
        
    try:
        render_short(video_path, json_path, output_path)
        return f"✅ Finalizat: {os.path.basename(output_path)}"
    except Exception as e:
        return f"❌ Eroare în {os.path.basename(folder)}: {str(e)}"

def main():
    print("=== AI Karaoke Studio: MoviePy Editor ===")
    root_dir = input("Calea către folderul rădăcină (ex: Prod): ").strip().strip('"')
    
    if not os.path.isdir(root_dir):
        print("❌ Folder invalid.")
        return

    # Încercăm să adăugăm ffmpeg în PATH vizibil pentru Whisper.
    try:
        import imageio_ffmpeg
        import shutil
        import sys
        
        ffmpeg_original = imageio_ffmpeg.get_ffmpeg_exe()
        # imageio_ffmpeg îl denumește gen "ffmpeg-win-x86_64.exe", deci îl vom copia local ca "ffmpeg.exe"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ffmpeg = os.path.join(script_dir, "ffmpeg.exe")
        
        if not os.path.exists(local_ffmpeg):
            print("📦 Pregătesc dependința FFmpeg...")
            shutil.copy(ffmpeg_original, local_ffmpeg)
            
        # Punem folderul scriptului în system PATH
        os.environ["PATH"] = script_dir + os.pathsep + os.environ["PATH"]
    except ImportError:
        pass

    # Încărcare Faster-Whisper
    print("⏳ Încarc Faster-Whisper (base, compute_type=int8)...")
    # compute_type="int8" este optim pentru CPU (Ryzen AI)
    # NOTĂ: Dacă treci pe NVIDIA în viitor, adaugă device="cuda" și compute_type="float16"
    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())

    # Identificăm dacă procesăm un singur folder sau o rădăcină cu subfoldere
    # Verificăm dacă există fișiere mp4 direct în folderul introdus
    mp4_in_root = [f for f in os.listdir(root_dir) if f.lower().endswith('.mp4') and not f.startswith('FINAL_')]
    
    if mp4_in_root:
        # Dacă există clipuri direct aici, procesăm doar acest folder
        subfolders = [root_dir]
        print(f"📂 Detectat folder individual: {os.path.basename(root_dir)}")
    else:
        # Altfel, căutăm subfoldere (comportamentul original)
        subfolders = [os.path.join(root_dir, d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
        subfolders.sort(key=lambda x: int(os.path.basename(x)) if os.path.basename(x).isdigit() else 0)
        print(f"📂 Detectate {len(subfolders)} subfoldere pentru procesare batch.")

    # Pasul 1: Transcriere
    print("\n--- PASUL 1: Transcriere & Generare JSON ---")
    for folder in subfolders:
        mp4_files = [f for f in os.listdir(folder) if f.lower().endswith('.mp4') and not f.startswith('FINAL_')]
        if not mp4_files: continue
        
        video_path = os.path.join(folder, mp4_files[0])
        json_path = os.path.join(folder, "transcript.json")
        
        if not os.path.exists(json_path):
            transcribe_video(model, video_path, json_path)
        else:
            print(f"⏭️ JSON deja existent în {os.path.basename(folder)}")

    print("\n✅ Transcrierea este gata!")
    print("⚠️ Acum poți deschide fișierele 'transcript.json' pentru a corecta manual cuvinte (ex: DOOMinos).")
    input("\nPresionează ENTER când ești gata să pornim randarea FINALĂ...")

    # Pasul 2: Randare în Paralel
    print(f"\n--- PASUL 2: Randare Video Shorts (PARALEL - 6 procese) ---")
    print(f"💡 Sfat: Pentru viteză MAXIMĂ, asigură-te că procesezi mai multe foldere deodată.")
    
    # Am urcat la 6 workers pentru a folosi la maxim CPU-ul Ryzen și cei 24GB RAM
    with ProcessPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(render_folder_task, subfolders))
        
    for res in results:
        print(res)

    print("\n🎉 Toate videoclipurile au fost randate!")

if __name__ == "__main__":
    main()
