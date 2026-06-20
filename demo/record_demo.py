"""Record Mimir MemoryAgent demo video from demo_terminal.html.

Uses Playwright to render the HTML terminal simulation and capture
it as frames, then ffmpeg to encode the MP4 video.

Output: demo/demo_video.mp4 — 1280x720, ~30fps, ~3 minutes
"""

import os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKDIR = Path(__file__).resolve().parent.parent
HTML_PATH = WORKDIR / "demo" / "demo_terminal.html"
OUTPUT_DIR = WORKDIR / "demo"
TMP_DIR = OUTPUT_DIR / ".frames"

# Configuration
WIDTH = 1280
HEIGHT = 720
FPS = 30
DURATION_SECONDS = 175  # ~2:55 — covers all 5 scenes with pauses
SCROLL_SPEED = 60  # pixels per second
TOTAL_FRAMES = DURATION_SECONDS * FPS


def main():
    print(f"Recording demo video: {DURATION_SECONDS}s at {FPS}fps")
    print(f"HTML: {HTML_PATH}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )

        # Load the HTML file
        page.goto(f"file://{HTML_PATH.absolute()}")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Get total scrollable height
        total_height = page.evaluate("document.body.scrollHeight")
        terminal_body = page.query_selector(".terminal-body")
        if terminal_body:
            terminal_element = page.query_selector(".terminal")
            if terminal_element:
                # Scroll within the terminal element
                scrollable = page.evaluate(
                    """() => {
                    const terminal = document.querySelector('.terminal-body');
                    return terminal ? terminal.scrollHeight - terminal.clientHeight : 0;
                }"""
                )
            else:
                scrollable = total_height - HEIGHT
        else:
            scrollable = total_height - HEIGHT

        print(f"Total height: {total_height}px, scrollable: {scrollable}px")

        # Calculate: how many pixels to scroll per frame to cover the content
        # We want to scroll through the content over DURATION_SECONDS
        pixels_per_frame = scrollable / TOTAL_FRAMES if TOTAL_FRAMES > 0 else 0

        print(f"Pixels per frame: {pixels_per_frame:.2f}")

        # Capture frames
        frame_count = 0
        scroll_position = 0
        start_time = time.time()

        for i in range(TOTAL_FRAMES):
            # Scroll
            scroll_position = min(i * pixels_per_frame, scrollable)
            page.evaluate(
                f"""() => {{
                const el = document.querySelector('.terminal-body');
                if (el) el.scrollTop = {scroll_position};
                else window.scrollTo(0, {scroll_position});
            }}"""
            )

            # Capture screenshot
            frame_path = TMP_DIR / f"frame_{i:05d}.png"
            page.screenshot(path=str(frame_path), full_page=False)
            frame_count += 1

            if i % 90 == 0:  # Report every 3 seconds
                elapsed = time.time() - start_time
                print(f"  Frame {i}/{TOTAL_FRAMES} ({i/TOTAL_FRAMES*100:.0f}%) — {elapsed:.1f}s")

        browser.close()

    print(f"\nFrames captured: {frame_count}")

    # Encode to MP4 with ffmpeg
    output_path = OUTPUT_DIR / "demo_video.mp4"
    print(f"Encoding to {output_path}...")

    cmd = (
        f"ffmpeg -y -framerate {FPS} -i {TMP_DIR}/frame_%05d.png "
        f"-c:v libx264 -preset fast -crf 23 "
        f"-pix_fmt yuv420p -r {FPS} "
        f"{output_path} 2>&1"
    )

    import subprocess
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    print(result.stdout[-500:] if result.stdout else "")
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr[-500:]}")
        print(f"Exit code: {result.returncode}")

    # Cleanup frames
    import shutil
    shutil.rmtree(TMP_DIR)

    # Report
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\nDone! Video: {output_path} ({size_mb:.1f} MB)")
    else:
        print("\nFailed to create video!")


if __name__ == "__main__":
    main()
