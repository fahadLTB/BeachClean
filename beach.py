import streamlit as st
import random

# --- Trash Items by Level ---
items_easy = {
    "Plastic Bottle 🍼": ("Recycle", "Plastic bottles take ~450 years to decompose."),
    "Banana Peel 🍌": ("Compost", "Banana peels decompose in a few weeks."),
    "Paper Bag 📄": ("Recycle", "Paper is one of the most recycled materials."),
}

items_medium = {
    "Glass Jar 🫙": ("Recycle", "Glass is 100% recyclable and can be reused forever."),
    "Styrofoam Cup ☕": ("Trash", "Styrofoam is non-recyclable and harmful."),
    "Apple Core 🍏": ("Compost", "Food scraps make great compost."),
}

items_hard = {
    "Battery 🔋": ("Trash", "Batteries must be disposed at special collection points."),
    "Pizza Box 🍕": ("Trash", "Greasy pizza boxes can’t be recycled."),
    "Aluminum Foil 🧻": ("Recycle", "Aluminum can be recycled, but must be clean."),
}

levels = {
    "Easy": items_easy,
    "Medium": items_medium,
    "Hard": items_hard
}

bins = ["Recycle", "Compost", "Trash"]
rounds_per_level = 5

# --- Initialize State ---
if "score" not in st.session_state:
    st.session_state.score = 0
if "round" not in st.session_state:
    st.session_state.round = 0
if "level" not in st.session_state:
    st.session_state.level = "Easy"
if "finished" not in st.session_state:
    st.session_state.finished = False

# --- UI ---
st.title("🌊 Beach Cleanup Trash Sorting Game")
st.write("Help clean the beach by sorting trash into the right bins!")

if not st.session_state.finished:
    # Get items for current level
    current_items = levels[st.session_state.level]
    item, (correct_bin, fact) = random.choice(list(current_items.items()))

    st.subheader(f"🗑️ What bin should this go in? **{item}**")
    choice = st.radio("Choose a bin:", bins, key="choice")

    if st.button("Submit"):
        st.session_state.round += 1
        if choice == correct_bin:
            st.session_state.score += 1
            st.success(f"✅ Correct! {fact}")
        else:
            st.error(f"❌ Wrong. {item} should go in **{correct_bin}**. {fact}")

        st.write(f"**Score:** {st.session_state.score}")

        # Level progression
        if st.session_state.round >= rounds_per_level:
            if st.session_state.level == "Easy":
                st.session_state.level = "Medium"
                st.session_state.round = 0
                st.info("🚀 Moving to Medium Level!")
            elif st.session_state.level == "Medium":
                st.session_state.level = "Hard"
                st.session_state.round = 0
                st.info("🔥 Moving to Hard Level!")
            else:
                st.session_state.finished = True

else:
    # --- Final Results ---
    st.subheader("🏆 Game Over!")
    st.write(f"Your final score: **{st.session_state.score} points**")

    if st.session_state.score >= 12:
        st.success("🌟 Amazing! You're an Eco-Hero!")
    elif st.session_state.score >= 8:
        st.info("💡 Good job! You know a lot about waste sorting.")
    else:
        st.warning("🌱 Keep learning! Every step helps the planet.")

    if st.button("🔄 Play Again"):
        st.session_state.score = 0
        st.session_state.round = 0
        st.session_state.level = "Easy"
        st.session_state.finished = False
