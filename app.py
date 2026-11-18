# -*- coding: utf-8 -*-
"""রাকিব সাবটাইটেল (Streamlit Community Cloud).

যেকোনো স্ক্রিপ্ট → রাকিব কণ্ঠের অডিও + সময় মিলিয়ে সাবটাইটেল (SRT/JSON)।
ASR (অডিও শুনে লেখা বের করা) কোথাও ব্যবহার করা হয় না — লেখা সবসময়
আপনার স্ক্রিপ্টেরটাই, তাই বাংলা ১০০% সঠিক থাকে। সময় আসে অডিও থেকে।

তিনটি পথ:
  A. স্ক্রিপ্ট → অডিও + সাবটাইটেল (সবচেয়ে নির্ভুল — প্রতি বাক্য আলাদা বানানো হয়)
  B. অডিও + স্ক্রিপ্ট → সাবটাইটেল (অডিওর নীরবতা ধরে বাক্যের সীমানা মেলানো হয়)
  C. স্ক্রিপ্ট + মোট সময় → সাবটাইটেল (আনুমানিক — অডিও না থাকলে)
"""
import time

import streamlit as st

import subtitle_tools as tools
import tts_engine

SAMPLE_SCRIPT = (
    "পররাষ্ট্র প্রতিমন্ত্রী শামা ওবায়েদ ইসলাম বলেছেন, নাগরিক হলেই পাসপোর্ট "
    "পাওয়া যাবে, এমন কোনো নিশ্চয়তা নেই। "
    "দণ্ডপ্রাপ্ত অপরাধী হলে সরকার পাসপোর্ট দিতে বাধ্য নয়। "
    "তিনি জানান, দুই হাজার চব্বিশ সালের জুলাই-আগস্টের ঘটনায় মানবতাবিরোধী "
    "অপরাধের দায়ে শেখ হাসিনা দোষী সাব্যস্ত হয়েছেন এবং তাকে মৃত্যুদণ্ড দেওয়া হয়েছে।"
)

AUDIO_EXTS = ["mp3", "wav", "m4a", "flac", "ogg", "aac"]


def show_segments(segments):
    for seg in segments:
        st.write(f"**{tools.srt_time(seg['start'])} → {tools.srt_time(seg['end'])}**  {seg['text']}")


def download_row(base: str, segments, duration: float, method: str,
                 wav_bytes: bytes | None = None):
    srt_text = tools.to_srt(segments)
    json_text = tools.to_json(f"{base}.wav", duration, segments, method)
    cols = st.columns(4 if wav_bytes else 3)
    with cols[0]:
        st.download_button("⬇️ SRT ডাউনলোড", srt_text, file_name=f"{base}.srt",
                           mime="text/plain", use_container_width=True)
    with cols[1]:
        st.download_button("⬇️ JSON ডাউনলোড", json_text, file_name=f"{base}.json",
                           mime="application/json", use_container_width=True)
    with cols[2]:
        st.download_button("⬇️ শুধু লেখা (.txt)", " ".join(s["text"] for s in segments),
                           file_name=f"{base}.txt", mime="text/plain",
                           use_container_width=True)
    if wav_bytes:
        with cols[3]:
            st.download_button("⬇️ অডিও (.wav)", wav_bytes, file_name=f"{base}.wav",
                               mime="audio/wav", use_container_width=True)
    with st.expander("📄 JSON দেখুন"):
        st.json(__import__("json").loads(json_text))


def main():
    st.set_page_config(page_title="রাকিব সাবটাইটেল", page_icon="🎙️", layout="centered")
    st.title("🎙️ রাকিব সাবটাইটেল")
    st.write("স্ক্রিপ্ট বা অডিও দিন — রাকিব কণ্ঠের সময় মিলিয়ে সাবটাইটেল (SRT / JSON) বানিয়ে দেবে। লেখা আপনার স্ক্রিপ্টেরটাই থাকে, তাই বাংলা ভুল হয় না।")

    mode = st.radio(
        "কীভাবে বানাবেন?",
        ["স্ক্রিপ্ট → অডিও + সাবটাইটেল (সবচেয়ে নির্ভুল)",
         "অডিও + স্ক্রিপ্ট → সাবটাইটেল",
         "স্ক্রিপ্ট + মোট সময় → সাবটাইটেল (আনুমানিক)"],
        index=0,
    )

    # ---- পথ A: স্ক্রিপ্ট থেকে অডিও + সাবটাইটেল -------------------------
    if mode.startswith("স্ক্রিপ্ট → অডিও"):
        if st.button("📰 নমুনা স্ক্রিপ্ট", use_container_width=False):
            st.session_state["script_a"] = SAMPLE_SCRIPT
        text = st.text_area("স্ক্রিপ্ট (বাংলায়, দাঁড়ি দিয়ে বাক্য শেষ করুন)",
                            value=st.session_state.get("script_a", SAMPLE_SCRIPT),
                            height=160, key="script_a")
        speed = st.selectbox("গতি", options=[0.75, 1.0, 1.25, 1.5], index=1,
                             format_func=lambda v: f"{v}x")
        if st.button("🎙️ অডিও + সাবটাইটেল বানাও", type="primary", use_container_width=True):
            text = (text or "").strip()
            if not text:
                st.warning("আগে স্ক্রিপ্ট লিখুন।")
            else:
                try:
                    with st.spinner("মডেল লোড হচ্ছে / অডিও বানানো হচ্ছে… (প্রথমবার মডেল নামতে একটু সময় লাগবে)"):
                        t0 = time.time()
                        tts_engine.ensure_model()
                        samples, segments, info = tools.synthesize_aligned(text, speed=speed)
                        total = time.time() - t0
                    wav = tts_engine.samples_to_wav_bytes(samples)
                    st.audio(wav, format="audio/wav", sample_rate=tts_engine.SAMPLE_RATE)
                    st.success(f"শেষ! {info['sentences']}টি বাক্য • মোট সময় "
                               f"{tools.format_duration(info['duration_s'])} • "
                               f"বানাতে লেগেছে {total:.0f} সেকেন্ড")
                    st.subheader("সাবটাইটেল")
                    show_segments(segments)
                    download_row("rakib_subtitles", segments, info["duration_s"],
                                 "script-to-audio", wav_bytes=wav)
                except Exception as exc:  # noqa: BLE001 - show the real error
                    st.error(f"বানানো যায়নি: {exc}")

    # ---- পথ B: অডিও + স্ক্রিপ্ট --------------------------------------
    elif mode.startswith("অডিও + স্ক্রিপ্ট"):
        uploaded = st.file_uploader("রাকিব কণ্ঠের অডিও ফাইল", type=AUDIO_EXTS)
        text = st.text_area("স্ক্রিপ্ট (অডিওতে যা বলা হয়েছে, হুবহু তাই লিখুন)",
                            height=160, key="script_b",
                            help="দাঁড়ি (।) দিয়ে প্রতিটা বাক্য শেষ করুন — বাক্যের সংখ্যা অডিওর বাক্যের সংখ্যার সমান হতে হবে।")
        if uploaded is not None:
            st.audio(uploaded)
        if st.button("📝 সাবটাইটেল বানাও", type="primary", use_container_width=True):
            if uploaded is None:
                st.warning("আগে অডিও ফাইল দিন।")
            elif not (text or "").strip():
                st.warning("আগে স্ক্রিপ্ট লিখুন।")
            else:
                try:
                    with st.spinner("অডিও পড়া হচ্ছে…"):
                        ext = uploaded.name.rsplit(".", 1)[-1].lower()
                        audio, rate = tools.decode_audio(uploaded.getbuffer().tobytes(), ext)
                    sentences = tools.split_sentences(text)
                    segments, exact, note = tools.align_audio_script(audio, rate, sentences)
                    duration = len(audio) / rate
                    if exact:
                        st.success(f"শেষ! {len(segments)}টি বাক্য • মোট সময় "
                                   f"{tools.format_duration(duration)} • {note}")
                    else:
                        st.warning(note)
                    st.subheader("সাবটাইটেল")
                    show_segments(segments)
                    base = uploaded.name.rsplit(".", 1)[0]
                    download_row(base, segments, duration, "audio+script")
                except Exception as exc:  # noqa: BLE001 - show the real error
                    st.error(f"বানানো যায়নি: {exc}")

    # ---- পথ C: স্ক্রিপ্ট + মোট সময় ------------------------------------
    else:
        text = st.text_area("স্ক্রিপ্ট (বাংলায়, দাঁড়ি দিয়ে বাক্য শেষ করুন)",
                            height=160, key="script_c")
        col1, col2 = st.columns(2)
        with col1:
            mins = st.number_input("মোট সময় — মিনিট", min_value=0, value=0, step=1)
        with col2:
            secs = st.number_input("মোট সময় — সেকেন্ড", min_value=0, value=0, step=1)
        if st.button("📝 সাবটাইটেল বানাও", type="primary", use_container_width=True):
            total = mins * 60 + secs
            if not (text or "").strip():
                st.warning("আগে স্ক্রিপ্ট লিখুন।")
            elif total <= 0:
                st.warning("মোট সময় দিন — কত মিনিটের অডিও, সেটা লিখুন।")
            else:
                sentences = tools.split_sentences(text)
                segments = tools.proportional_segments(sentences, float(total))
                st.warning("এটা আনুমানিক সময় — মোট সময় বাক্যের দৈর্ঘ্য অনুযায়ী ভাগ করে "
                           "দেওয়া হয়েছে। নির্ভুল সময় চাইলে স্ক্রিপ্ট থেকে অডিও বানান, "
                           "অথবা অডিও আপলোড করুন।")
                st.success(f"শেষ! {len(segments)}টি বাক্য • মোট সময় "
                           f"{tools.format_duration(float(total))}")
                st.subheader("সাবটাইটেল")
                show_segments(segments)
                download_row("rakib_subtitles", segments, float(total),
                             "script+duration")


if __name__ == "__main__":
    main()
