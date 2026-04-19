import os
import json
import whisper
import time
import numpy as np
from moviepy import VideoFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoClip
import render_utils

# -= Configurare Layout =-
CANVAS_W = 1080
CANVAS_H = 1920
VIDEO_Y = 400
SUBS_Y_BASE = 1400

# Dicționar pentru corecții automate
AUTOCORRECT = {
    "dominos": "DOOMinos",
    "youtube": "YouTube",
    "shorts": "Shorts"
}

def apply_autocorrect(text):
    words = text.split()
    new_words = [AUTOCORRECT.get(w.lower().strip(".,!?"), w) for w in words]
    return " ".join(new_words)

def transcribe_video(model, video_path, json_path):
    """Pasul 1: Transcrierea video-ului și generarea fișierului JSON."""
    print(f"🎤 [Whisper] Analizez: {os.path.basename(video_path)}...")
    result = model.transcribe(video_path, word_timestamps=True)
    
    segments = []
    for seg in result.get("segments", []):
        words = []
        for w in seg.get("words", []):
            clean_word = apply_autocorrect(w['word'].strip())
            words.append({
                "word": clean_word,
                "start": w['start'],
                "end": w['end']
            })
        
        segments.append({
            "start": seg['start'],
            "end": seg['end'],
            "words": words
        })
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=4, ensure_ascii=False)
    
    print(f"✅ JSON salvat: {os.path.basename(json_path)}")

def render_short(video_path, json_path, output_path):
    """Pasul 2: Randarea finală folosind MoviePy."""
    print(f"🎬 [MoviePy] Randez formatul Shorts pentru: {os.path.basename(video_path)}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        segments = json.load(f)
        
    video = VideoFileClip(video_path)
    # Rezoluția 16:9 de intrare
    orig_w, orig_h = video.size
    
    # Scale video la lățimea 1080
    video_scaled = video.resized(width=CANVAS_W)
    scaled_w, scaled_h = video_scaled.size
    
    # Fundal negru
    background = ColorClip(size=(CANVAS_W, CANVAS_H), color=(0,0,0), duration=video.duration)
    
    # Poziționăm video-ul principal
    video_final = video_scaled.with_position((0, VIDEO_Y))
    
    # Bara de progres de sus
    def make_progress(t):
        img = render_utils.generate_progress_frame(CANVAS_W, t, video.duration)
        return np.array(img)
    
    progress_bar = VideoClip(make_progress, duration=video.duration).with_position((0, 0))

    # Creăm clipurile pentru subtitrări Karaoke
    karaoke_clips = []
    for seg in segments:
        def make_frame(t, current_seg=seg):
            # Adăugăm timpul de start al segmentului pentru că MoviePy trimite t relativ la clip
            # Dar aici frame-ul va fi creat pentru întreaga durată a segmentului
            img = render_utils.generate_karaoke_frame(CANVAS_W, CANVAS_H, current_seg, t + current_seg['start'])
            return np.array(img)[:, :, :3] # RGB

        def make_mask(t, current_seg=seg):
            img = render_utils.generate_karaoke_frame(CANVAS_W, CANVAS_H, current_seg, t + current_seg['start'])
            return np.array(img)[:, :, 3] / 255.0 # Alpha mask

        duration = seg['end'] - seg['start']
        if duration <= 0: continue
        
        txt_clip = VideoClip(make_frame, duration=duration).with_mask(VideoClip(make_mask, is_mask=True, duration=duration))
        txt_clip = txt_clip.with_start(seg['start'])
        karaoke_clips.append(txt_clip)
        
    # Injectare CTA (Call to Action)
    # Punem CTA1 la segmentul 2 și CTA2 la segmentul 3 (dacă există)
    cta_clips = []
    if len(segments) >= 2:
        seg_cta1 = segments[1]
        cta1_img = render_utils.generate_cta_frame(CANVAS_W, CANVAS_H, "Enjoying? 👍", (750, 1020))
        cta1 = ImageClip(np.array(cta1_img)[:,:,:3]).with_mask(ImageClip(np.array(cta1_img)[:,:,3]/255.0, is_mask=True))
        cta1 = cta1.with_start(seg_cta1['start']).with_duration(seg_cta1['end'] - seg_cta1['start'])
        cta_clips.append(cta1)
        
    if len(segments) >= 3:
        seg_cta2 = segments[2]
        cta2_img = render_utils.generate_cta_frame(CANVAS_W, CANVAS_H, "Join the squad! ➔", (600, 1580))
        cta2 = ImageClip(np.array(cta2_img)[:,:,:3]).with_mask(ImageClip(np.array(cta2_img)[:,:,3]/255.0, is_mask=True))
        cta2 = cta2.with_start(seg_cta2['start']).with_duration(seg_cta2['end'] - seg_cta2['start'])
        cta_clips.append(cta2)

    # Compoziția finală
    result = CompositeVideoClip([background, video_final, progress_bar] + karaoke_clips + cta_clips)
    
    # Export (folosim libx264 pentru compatibilitate maximă AMD/Ryzen)
    # NOTĂ: Dacă treci pe NVIDIA în viitor, schimbă codec="libx264" cu codec="h264_nvenc" pentru viteză 10x
    result.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True)
    video.close()
    result.close()

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

    # Încărcare Whisper
    print("⏳ Încarc Whisper (base)...")
    # NOTĂ: Dacă treci pe NVIDIA în viitor, adaugă device="cuda" în load_model
    model = whisper.load_model("base")

    subfolders = [os.path.join(root_dir, d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
    subfolders.sort(key=lambda x: int(os.path.basename(x)) if os.path.basename(x).isdigit() else 0)

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

    # Pasul 2: Randare
    print("\n--- PASUL 2: Randare Video Shorts ---")
    for folder in subfolders:
        mp4_files = [f for f in os.listdir(folder) if f.lower().endswith('.mp4') and not f.startswith('FINAL_')]
        if not mp4_files: continue
        
        video_path = os.path.join(folder, mp4_files[0])
        json_path = os.path.join(folder, "transcript.json")
        output_path = os.path.join(folder, f"FINAL_SHORT_{os.path.basename(folder)}.mp4")
        
        if os.path.exists(output_path):
            print(f"⏭️ Skip: {os.path.basename(output_path)} există deja.")
            continue
            
        render_short(video_path, json_path, output_path)

    print("\n🎉 Toate videoclipurile au fost randate!")

if __name__ == "__main__":
    main()
