import streamlit as st
from datetime import datetime
from ai_meal_planner import generate_meal_plan
from database import (
    init_db,
    register_user,
    verify_login,
    save_user_profile,
    save_meal_plan,
    get_meal_plans,
)

# ---------------------------------------------------------
# DATABASE INITIALIZATION (creates tables on first run)
# ---------------------------------------------------------
init_db()

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Nutrition Planner",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------
st.markdown("""
<style>

    /* Main application background */
    .stApp {
        background: linear-gradient(135deg, #f7fff9 0%, #eefaf2 100%);
    }

    /* Main content */
    .main {
        padding: 2rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #143d2a 0%, #1f6040 100%);
    }

    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: white !important;
    }

    /* Sidebar navigation radio buttons */
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: rgba(255, 255, 255, 0.08);
        padding: 12px 15px;
        border-radius: 10px;
        margin-bottom: 8px;
        transition: 0.3s;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: rgba(255, 255, 255, 0.18);
    }

    /* Main title */
    .main-title {
        font-size: 42px;
        font-weight: 800;
        color: #14532d;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #4b6354;
        margin-bottom: 25px;
    }

    /* Cards */
    .info-card {
        background-color: white;
        padding: 25px;
        border-radius: 18px;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
        margin-bottom: 20px;
        border-left: 5px solid #2e8b57;
    }

    /* Section headings */
    .section-title {
        font-size: 26px;
        font-weight: 700;
        color: #14532d;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #2e8b57, #3ca86b);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 25px;
        font-size: 16px;
        font-weight: 600;
        transition: 0.3s;
    }

    .stButton > button:hover {
        background: linear-gradient(90deg, #256f46, #318c59);
        transform: translateY(-2px);
    }

    /* Form */
    div[data-testid="stForm"] {
        background-color: white;
        padding: 25px;
        border-radius: 18px;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.07);
    }

    /* Metrics */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06);
    }

</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# LOGIN / SIGNUP GATE
# ---------------------------------------------------------
if "user_id" not in st.session_state:

    st.markdown(
        '<div class="main-title">🥗 AI Nutrition Planner</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="subtitle">Please log in or create an account to continue.</div>',
        unsafe_allow_html=True
    )

    login_tab, signup_tab = st.tabs(["🔑 Login", "📝 Sign Up"])

    with login_tab:
        with st.form("login_form"):
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("Log In")

        if login_submitted:
            user = verify_login(login_username, login_password)
            if user:
                st.session_state["user_id"] = user["user_id"]
                st.session_state["username"] = user["username"]
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with signup_tab:
        with st.form("signup_form"):
            signup_username = st.text_input("Choose a username", key="signup_username")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Choose a password", type="password", key="signup_password")
            signup_submitted = st.form_submit_button("Create Account")

        if signup_submitted:
            if not signup_username.strip() or not signup_password:
                st.error("Username and password are required.")
            else:
                try:
                    new_user_id = register_user(signup_username, signup_email, signup_password)
                    st.session_state["user_id"] = new_user_id
                    st.session_state["username"] = signup_username
                    st.success("Account created! Redirecting...")
                    st.rerun()
                except Exception:
                    st.error("That username or email is already taken.")

    st.stop()  # Don't render the rest of the app until logged in


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.markdown(
    """
    <div style="text-align:center; padding:15px 0 25px 0;">
        <div style="font-size:50px;">🥗</div>
        <h2 style="color:white; margin-bottom:5px;">
            AI Nutrition Planner
        </h2>
        <p style="color:#d7f5df; font-size:14px;">
            Smart • Personalized • Healthy
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("### Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "🏠 Home",
        "👤 Profile",
        "📊 Health Analysis",
        "🥗 Meal Planner",
        "📜 Previous Plans",
        "ℹ️ About"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"Logged in as **{st.session_state['username']}**")
if st.sidebar.button("🚪 Log Out"):
    for key in ["user_id", "username"]:
        st.session_state.pop(key, None)
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.info(
    "This application provides educational nutrition "
    "recommendations and is not a substitute for professional "
    "medical or dietary advice."
)


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------
if page == "🏠 Home":

    st.markdown(
        '<div class="main-title">🥗 AI Nutrition Planner</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Your personalized AI-powered nutrition and meal planning assistant.'
        '</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="info-card">
                <h3>👤 Personalized</h3>
                <p>
                Recommendations based on your age, height, weight,
                activity level, goals and dietary preferences.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="info-card">
                <h3>📊 Health Analysis</h3>
                <p>
                Calculate BMI, calorie requirements and
                recommended nutrient intake.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="info-card">
                <h3>🤖 AI Meal Planning</h3>
                <p>
                Generate customized meal plans, recipes and
                healthy alternatives using AI.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        """
        <div class="info-card">
            <h2>How It Works</h2>
            <p><b>1.</b> Enter your personal information</p>
            <p><b>2.</b> Analyze your health and nutritional requirements</p>
            <p><b>3.</b> Match foods with your dietary preferences</p>
            <p><b>4.</b> Generate an AI-powered personalized meal plan</p>
            <p><b>5.</b> Save and review your previous plans</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.success("👈 Use the sidebar to create your nutrition profile.")


# ---------------------------------------------------------
# PROFILE PAGE
# ---------------------------------------------------------
elif page == "👤 Profile":

    st.markdown(
        '<div class="main-title">👤 User Profile</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Enter your information to receive personalized recommendations.'
        '</div>',
        unsafe_allow_html=True
    )

    with st.form("user_form"):

        st.markdown(
            '<div class="section-title">Personal Information</div>',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:

            name = st.text_input("Name")

            age = st.number_input(
                "Age",
                min_value=1,
                max_value=120,
                value=20
            )

            gender = st.selectbox(
                "Gender",
                ["Male", "Female", "Other"]
            )

        with col2:

            height = st.number_input(
                "Height (cm)",
                min_value=50.0,
                max_value=250.0,
                value=165.0
            )

            weight = st.number_input(
                "Weight (kg)",
                min_value=10.0,
                max_value=300.0,
                value=60.0
            )

        st.markdown(
            '<div class="section-title">Lifestyle & Diet</div>',
            unsafe_allow_html=True
        )

        col3, col4 = st.columns(2)

        with col3:

            activity_level = st.selectbox(
                "Activity Level",
                [
                    "Sedentary",
                    "Lightly Active",
                    "Moderately Active",
                    "Very Active",
                    "Extremely Active"
                ]
            )

            dietary_preference = st.selectbox(
                "Dietary Preference",
                [
                    "Vegetarian",
                    "Non-Vegetarian",
                    "Vegan",
                    "Eggetarian"
                ]
            )

        with col4:

            fitness_goal = st.selectbox(
                "Fitness Goal",
                [
                    "Weight Loss",
                    "Weight Maintenance",
                    "Weight Gain",
                    "Muscle Gain"
                ]
            )

            allergies = st.text_input(
                "Allergies (if any)",
                placeholder="Example: peanuts, lactose"
            )

        meals_per_day = st.selectbox(
            "Meals per day",
            [3, 4, 5],
            index=0
        )

        submitted = st.form_submit_button(
            "🔍 Analyze My Nutrition"
        )

    if submitted:

        if not name.strip():

            st.error("Please enter your name.")

        else:

            # Save information in session state
            st.session_state["name"] = name
            st.session_state["age"] = age
            st.session_state["gender"] = gender
            st.session_state["height"] = height
            st.session_state["weight"] = weight
            st.session_state["activity_level"] = activity_level
            st.session_state["dietary_preference"] = dietary_preference
            st.session_state["fitness_goal"] = fitness_goal
            st.session_state["allergies"] = allergies
            st.session_state["meals_per_day"] = meals_per_day

            # Persist to the database as well, so it survives across sessions
            save_user_profile(st.session_state["user_id"], {
                "age": age,
                "gender": gender,
                "height_cm": height,
                "weight_kg": weight,
                "activity_level": activity_level,
                "dietary_preference": dietary_preference,
                "fitness_goal": fitness_goal,
                "allergies": allergies,
            })

            st.success(
                "✅ Profile saved successfully!"
            )

            st.markdown(
                """
                <div class="info-card">
                    <h3>Your Profile</h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Name", name)
                st.metric("Age", age)
                st.metric("Gender", gender)

            with col2:
                st.metric("Height", f"{height} cm")
                st.metric("Weight", f"{weight} kg")
                st.metric("Activity", activity_level)

            with col3:
                st.metric("Diet", dietary_preference)
                st.metric("Goal", fitness_goal)
                st.metric(
                    "Allergies",
                    allergies if allergies else "None"
                )


# ---------------------------------------------------------
# HEALTH ANALYSIS PAGE
# ---------------------------------------------------------
elif page == "📊 Health Analysis":

    st.markdown(
        '<div class="main-title">📊 Health Analysis</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Your health and nutritional analysis will appear here.'
        '</div>',
        unsafe_allow_html=True
    )

    if "weight" not in st.session_state:

        st.warning(
            "Please complete your profile first."
        )

        st.info(
            "Go to 👤 Profile from the sidebar."
        )

    else:

        weight = st.session_state["weight"]
        height = st.session_state["height"]
        age = st.session_state["age"]
        gender = st.session_state["gender"]
        activity_level = st.session_state["activity_level"]

        # BMI calculation
        height_m = height / 100

        bmi = weight / (height_m ** 2)

        # Basic BMR calculation
        if gender == "Male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        # ---- Placeholder TDEE + macro targets -------------------------
        # NOTE: this is a simple placeholder calculation standing in for
        # a dedicated TDEE/macro-target module. Replace this block if a
        # more precise one is built later — the AI meal planner only
        # needs calorie_target / protein_target / carbs_target /
        # fat_target to be present in session_state, however computed.
        activity_multipliers = {
            "Sedentary": 1.2,
            "Lightly Active": 1.375,
            "Moderately Active": 1.55,
            "Very Active": 1.725,
            "Extremely Active": 1.9,
        }
        tdee = bmr * activity_multipliers.get(activity_level, 1.2)
        calorie_target = tdee
        protein_target = (0.3 * calorie_target) / 4   # 30% of kcal, 4 kcal/g protein
        fat_target = (0.25 * calorie_target) / 9       # 25% of kcal, 9 kcal/g fat
        carbs_target = (0.45 * calorie_target) / 4     # 45% of kcal, 4 kcal/g carb
        # -----------------------------------------------------------------

        # Persist so the Meal Planner page can use these without recomputing
        st.session_state["bmi"] = bmi
        st.session_state["bmr"] = bmr
        st.session_state["tdee"] = tdee
        st.session_state["calorie_target"] = calorie_target
        st.session_state["protein_target"] = protein_target
        st.session_state["carbs_target"] = carbs_target
        st.session_state["fat_target"] = fat_target

        # Persist the calculated metrics onto the user's profile row too,
        # so they survive across sessions/logins.
        save_user_profile(st.session_state["user_id"], {
            "age": age,
            "gender": gender,
            "height_cm": height,
            "weight_kg": weight,
            "activity_level": st.session_state.get("activity_level"),
            "dietary_preference": st.session_state.get("dietary_preference"),
            "fitness_goal": st.session_state.get("fitness_goal"),
            "allergies": st.session_state.get("allergies"),
            "bmi": bmi,
            "daily_calories": calorie_target,
            "protein_g": protein_target,
            "carbs_g": carbs_target,
            "fat_g": fat_target,
        })

        st.markdown(
            '<div class="section-title">Your Health Metrics</div>',
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "BMI",
                f"{bmi:.2f}"
            )

        with col2:
            st.metric(
                "BMR",
                f"{bmr:.0f} kcal/day"
            )

        with col3:
            st.metric(
                "TDEE",
                f"{tdee:.0f} kcal/day"
            )

        if bmi < 18.5:
            category = "Underweight"

        elif bmi < 25:
            category = "Normal Weight"

        elif bmi < 30:
            category = "Overweight"

        else:
            category = "Obesity"

        st.info(
            f"Your BMI category is **{category}**."
        )

        st.markdown(
            '<div class="section-title">Daily Nutrition Targets</div>',
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Protein target", f"{protein_target:.0f} g")
        with col2:
            st.metric("Carbs target", f"{carbs_target:.0f} g")
        with col3:
            st.metric("Fat target", f"{fat_target:.0f} g")


# ---------------------------------------------------------
# MEAL PLANNER PAGE
# ---------------------------------------------------------
elif page == "🥗 Meal Planner":

    st.markdown(
        '<div class="main-title">🥗 AI Meal Planner</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Your personalized AI-generated meal plan will appear here.'
        '</div>',
        unsafe_allow_html=True
    )

    if "name" not in st.session_state:

        st.warning(
            "Please create your profile first."
        )

    elif "calorie_target" not in st.session_state:

        st.warning(
            "Please complete the 📊 Health Analysis step first, "
            "so your nutrition targets are available."
        )

    else:

        st.success(
            f"Welcome, {st.session_state['name']}! "
            "Your meal planner is ready."
        )

        st.markdown(
            """
            <div class="info-card">
                <h3>🤖 AI Meal Planning</h3>
                <p>
                Click below to generate a personalized breakfast, lunch,
                snacks and dinner plan based on your nutritional
                requirements, using the Mistral API.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ---- Build user_data from session_state -----------------------
        raw_allergies = st.session_state.get("allergies", "")
        allergies_list = [
            a.strip() for a in raw_allergies.split(",") if a.strip()
        ] if raw_allergies else []

        user_data = {
            "age": st.session_state["age"],
            "gender": st.session_state["gender"],
            "height": st.session_state["height"],
            "weight": st.session_state["weight"],
            "bmi": st.session_state["bmi"],
            "bmr": st.session_state["bmr"],
            "tdee": st.session_state["tdee"],
            "calorie_target": st.session_state["calorie_target"],
            "protein_target": st.session_state["protein_target"],
            "carbs_target": st.session_state["carbs_target"],
            "fat_target": st.session_state["fat_target"],
            "diet": st.session_state["dietary_preference"],
            "allergies": allergies_list,
            "avoid_foods": [],
            "meals_per_day": st.session_state.get("meals_per_day", 3),
        }

        # ---- recommended_foods placeholder -----------------------------
        # NOTE: this stands in for a teammate-owned Random Forest module.
        # Swap this list for whatever that module returns, e.g.:
        #   recommended_foods = st.session_state["rf_recommended_foods"]
        recommended_foods = st.session_state.get(
            "rf_recommended_foods",
            [
                {"food": "Oats", "calories": 150, "protein": 5},
                {"food": "Paneer", "calories": 265, "protein": 18},
                {"food": "Banana", "calories": 105, "protein": 1.3},
                {"food": "Lentils (Dal)", "calories": 230, "protein": 18},
                {"food": "Brown Rice", "calories": 215, "protein": 5},
            ]
        )
        # -----------------------------------------------------------------

        if st.button("✨ Generate Personalized Meal Plan"):

            with st.spinner("Generating your personalized meal plan..."):
                meal_plan = generate_meal_plan(user_data, recommended_foods)

            st.session_state["last_meal_plan"] = meal_plan

            # Persist to SQLite so it shows up in Previous Plans across sessions.
            db_items = []
            for meal in meal_plan.get("meals", []):
                for food in meal.get("foods", []):
                    db_items.append({
                        "meal_type": meal.get("meal", "Meal").lower(),
                        "food_name": food.get("name", "Unknown item"),
                        "calories": food.get("calories"),
                        "protein_g": food.get("protein_g"),
                        "carbs_g": food.get("carbs_g"),
                        "fat_g": food.get("fat_g"),
                        "recipe_text": food.get("quantity", ""),
                    })

            ai_summary = "; ".join(meal_plan.get("notes", [])) or "AI-generated daily meal plan."
            plan_date = str(datetime.utcnow().date())
            save_meal_plan(st.session_state["user_id"], plan_date, ai_summary, db_items)

        if "last_meal_plan" in st.session_state:

            meal_plan = st.session_state["last_meal_plan"]

            if meal_plan.get("is_fallback"):
                st.warning(
                    "AI meal generation was unavailable, so a simple plan "
                    "was built directly from your recommended foods instead."
                )
                with st.expander("Why did this happen? (diagnostic info)"):
                    st.write("**Reason:**", meal_plan.get("error_reason"))
                    diag = meal_plan.get("diagnostics", {})
                    if diag:
                        st.write("**Python executable:**", diag.get("python_executable"))
                        st.write("**Gemini SDK importable:**", diag.get("gemini_sdk_available"))
                        st.write("**Import error:**", diag.get("gemini_import_error"))
                        st.write("**API key present:**", diag.get("api_key_present"))

            st.markdown("## 🍽️ Your Personalized Meal Plan")

            meal_icons = {
                "Breakfast": "🌅",
                "Lunch": "☀️",
                "Snack": "🍎",
                "Dinner": "🌙",
            }

            for meal in meal_plan.get("meals", []):
                icon = meal_icons.get(meal["meal"], "🍽️")
                st.markdown(f"### {icon} {meal['meal']}")

                for food in meal.get("foods", []):
                    qty = f" — {food['quantity']}" if food.get("quantity") else ""
                    st.markdown(f"* {food['name']}{qty}")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(
                        f"**Calories:** {meal.get('meal_calories', '—')} kcal"
                    )
                with col2:
                    protein_sum = sum(
                        (f.get("protein_g") or 0) for f in meal.get("foods", [])
                    )
                    st.markdown(f"**Protein:** {protein_sum:.0f} g")

            st.markdown("---")
            st.markdown("### 📊 Daily Nutrition Summary")
            summary = meal_plan.get("daily_summary", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Calories", f"{summary.get('calories', '—')} kcal")
            c2.metric("Protein", f"{summary.get('protein_g', '—')} g")
            c3.metric("Carbs", f"{summary.get('carbs_g', '—')} g")
            c4.metric("Fat", f"{summary.get('fat_g', '—')} g")

            if meal_plan.get("notes"):
                st.markdown("### 📝 Notes")
                for note in meal_plan["notes"]:
                    st.info(note)

            st.caption(meal_plan.get("disclaimer", ""))


# ---------------------------------------------------------
# PREVIOUS PLANS PAGE
# ---------------------------------------------------------
elif page == "📜 Previous Plans":

    st.markdown(
        '<div class="main-title">📜 Previous Plans</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'View your previously generated meal plans.'
        '</div>',
        unsafe_allow_html=True
    )

    plans = get_meal_plans(st.session_state["user_id"])

    if not plans:
        st.info("No saved meal plans yet. Generate one from 🥗 Meal Planner!")
    else:
        for plan in plans:
            with st.expander(f"📅 {plan['plan_date']} — {plan['ai_summary']}"):
                for item in plan["items"]:
                    st.markdown(
                        f"**{item['meal_type'].title()}**: {item['food_name']} "
                        f"({item['calories']} kcal, "
                        f"P {item['protein_g']}g / C {item['carbs_g']}g / F {item['fat_g']}g)"
                    )
                    if item.get("recipe_text"):
                        st.caption(item["recipe_text"])


# ---------------------------------------------------------
# ABOUT PAGE
# ---------------------------------------------------------
elif page == "ℹ️ About":

    st.markdown(
        '<div class="main-title">ℹ️ About the Project</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="info-card">
            <h2>🥗 AI Nutrition Planner</h2>

            <p>
            AI Nutrition Planner is a Streamlit-based Python
            application designed to provide personalized nutrition
            recommendations and AI-powered meal planning.
            </p>

            <h3>Technology Used</h3>

            <p>🐍 Python</p>
            <p>🎨 Streamlit</p>
            <p>📊 Pandas & NumPy</p>
            <p>🤖 Machine Learning</p>
            <p>🧠 Mistral AI</p>
            <p>🗄️ SQLite Database</p>
            <p>📈 Plotly</p>

            <h3>Purpose</h3>

            <p>
            The system analyzes user information such as age,
            height, weight, activity level, dietary preference
            and fitness goal to provide personalized nutritional
            recommendations.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.warning(
        "⚠️ This application is for educational purposes only "
        "and should not be considered medical advice."
    )
