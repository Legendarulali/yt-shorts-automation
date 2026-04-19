import os
import numpy as np
from moviepy import VideoFileClip, CompositeVideoClip, ImageClip, VideoClip
from concurrent.futures import ProcessPoolExecutor
import render_utils

# -= Configurare Layout Final =-
CANVAS_W = 1080
CANVAS_H = 1920

def finalize_single_short(video_path, output_path):
    """Adaugă progres bar și CTA-uri pe un fragment de 60s."""
    print(f"✨ Finalizez: {os.path.basename(video_path)}...")
    
    video = VideoFileClip(video_path)
    
    # Filtrare: Procesăm doar dacă video-ul este vertical (Shorts style)
    if video.w > video.h:
        print(f"⏭️ Skip: {os.path.basename(video_path)} nu este vertical (16:9).")
        video.close()
        return f"⏭️ Ignorat (16:9): {os.path.basename(video_path)}"
        
    duration = video.duration
    
    # 1. Bara de progres (10px)
    def make_progress(t):
        # Mărim bara la 30px conform cerinței
        img = render_utils.generate_progress_frame(CANVAS_W, t, duration, height=30)
        return np.array(img)
    
    progress_bar = VideoClip(make_progress, duration=duration).with_position((0, 0))
    
    # 2. CTA-uri dinamice
    # Enjoying? (durată 4 secunde)
    cta_clips = []
    if duration > 10:
        cta1_img = render_utils.generate_cta_frame(CANVAS_W, CANVAS_H, "Enjoying? ➔", (650, 925))
        cta1 = ImageClip(np.array(cta1_img)[:,:,:3]).with_mask(ImageClip(np.array(cta1_img)[:,:,3]/255.0, is_mask=True))
        # În MoviePy 2.0, efectele de fade se pun cu with_effects
        from moviepy.video.fx import FadeIn, FadeOut
        cta1 = cta1.with_start(10).with_duration(5).with_effects([FadeIn(0.4), FadeOut(0.4)])
        cta_clips.append(cta1)
    
    # Join the squad!(durată 5 secunde)
    if duration > 15:
        cta2_img = render_utils.generate_cta_frame(CANVAS_W, CANVAS_H, "Join the squad! ↴", (100, 1550))
        cta2 = ImageClip(np.array(cta2_img)[:,:,:3]).with_mask(ImageClip(np.array(cta2_img)[:,:,3]/255.0, is_mask=True))
        from moviepy.video.fx import FadeIn, FadeOut
        cta2 = cta2.with_start(10).with_duration(5).with_effects([FadeIn(0.4), FadeOut(0.4)])
        cta_clips.append(cta2)

    # Compoziția finală
    final = CompositeVideoClip([video, progress_bar] + cta_clips)
    
    # Export Turbo viteză maximă
    final.write_videofile(
        output_path, 
        fps=30, 
        codec="h264_amf", 
        audio_codec="aac", 
        temp_audiofile="temp-final-audio.m4a",
        remove_temp=True,
        preset="balanced",
        threads=os.cpu_count(),
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    
    video.close()
    final.close()
    return f"✅ Gata: {os.path.basename(output_path)}"

def main():
    print("=== AI Karaoke Studio: ETAPA 2 (Finalizator) ===")
    input_dir = input("Calea către folderul cu fragmentele tăiate (din Premiere): ").strip().strip('"')
    
    if not os.path.exists(input_dir):
        print("❌ Folder invalid.")
        return

    output_dir = os.path.join(input_dir, "FINALIZATE")
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    mp4_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.mp4') and os.path.isfile(os.path.join(input_dir, f))]
    
    if not mp4_files:
        print("❌ Nu am găsit fișiere .mp4 în folder.")
        return

    print(f"🚀 Pornesc finalizarea pentru {len(mp4_files)} clipuri în paralel...")
    
    # Procesare în paralel pentru viteză maximă
    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = []
        for video_path in mp4_files:
            out_name = "UPLOAD_" + os.path.basename(video_path)
            out_path = os.path.join(output_dir, out_name)
            futures.append(executor.submit(finalize_single_short, video_path, out_path))
            
        for f in futures:
            print(f.result())

    print("\n🎉 Totul este gata de UPLOAD! Succes! 🚀")

if __name__ == "__main__":
    main()
