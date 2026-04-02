# 🧠 Academic Success Planner
A Smart academic decision-support system for course scheduling and workload optimization.


## 📌 Problem
Students often build course schedules based on availability — not outcomes. They lack insight into:
- Workload balance
- Burnout risk
- Impact on academic performance
- Tradeoffs between different course combinations

As a result, students may unintentionally create schedules that lead to overload, poor performance, or burnout.


## 💡 Solution
The Academic Success Planner is a decision-support system that helps students:
- Build course schedules
- Evaluate workload and difficulty
- Predict academic performance risk
- Compare alternative schedules
- Make informed, optimized decisisons

This system aims to help students make better academic decisions by transforming course selection from a trial-and-error process into a data-informed planning experience.


## ⚙️ What This Project Does
This system goes beyond traditional course registration by helping students evaluate and optimize their schedules based on workload, risk, and academic outcomes.
- Enables students to create and manage course schedules
- Applies real-world constraints (capacity, prerequisites, waitlists)
- Estimates workload and schedule difficulty
- Identifies high-risk (oveloaded) schedules
- Recommends improved course combinations
- Explains why certain schedules are better


## 🧩 Key Features

### 🧱 Core System
The current platform supports core course registration workflows, including:
- Browse available courses and view detailed course information
- Filter courses based on criteria such as department or availability
- Register for and drop classes in real time
- Join waitlists for courses that have reached capacity

### ⚙️ Backend Logic & Constraints
The backend enforces key registration rules to maintain a consistent system state, including:
- Enrollment caps per course
- Automatic waitlisting when courses reach capacity
- Prevention of duplicate enrollments
- Server-side validation of schedule updates
- Prerequisite validation and registration rule enforcement

These constraints are handled through application logic and database-backed validation to ensure reliability regardless of frontend behavior.

### 🧠 Intelligence Layer (In Progress)
The next phase of development expands the system from registration into academic planning and decision support:
- Workload estimation using course difficulty modeling
- Burnout risk detection for overloaded schedules
- GPA / performance prediction (planned)
- Schedule optimization and personalized recommendations

### 🔄 Decision Engine (Planned)
To support better academic decision-making, future versions will include:
- Comparison of multiple schedule options
- Alternative course combination suggestions
- Tradeoff analysis across workload, difficulty, and expected performance

### 📊 Explainability (Planned)
To make recommendations more transparent, the system will explain:
- Why a schedule is recommended
- Why a schedule may lead to overload
- What tradeoffs exist between different schedule choices


## 🏗️ System Architecture & Tech Stack
The system separates user-specific planning data from academic course data within a structured relational database, enabling consistent constraint enforcement and a foundation for future integration with external data sources.

Frontend: HTML/CSS  
Backend: Python (Flask)  
Database: SQLite  
Concepts:
- RESTful routing
- Server-side validation
- Relational data modeling
- Constraint-based logic


## ⚙️ Running Locally
To run this project locally:
1. Ensure Python (3.9+) and SQLite are installed on your machine.
2. Clone the repository and navigate to the project directory.
3. Create and activate a virtual environment, then install the required dependencies by running `pip install -r requirements.txt` in your terminal.
4. Create a .env file in the root directory by copying from .env.example and update the following values:  
   a. SQLITE3_DB = name of your local database file (e.g., academic_success_planner.db)  
   b. SECRET_KEY = any random secure string
5. Create a .flaskenv file in the root directory by copying from .flaskenv.example and update the following values:  
   a. FLASK_APP = name of the app (e.g., course_reg)  
   b. SECRET_KEY = any random secure string (e.g., development)  
6. Create an empty SQLite database file in the project root using the name specified in .env.
7. Start the Flask development server by running `flask run` in your terminal.
8. Open the application in your browser at http://127.0.0.1:5000.
9. You should now be able to use the dashboard locally to view, add, drop, and waitlist courses.

### 📊 Database Setup
The application uses a relational SQLite database with tables for courses, departments, instructors, and student schedules.  
The database file is defined using the SQLITE3_DB variable in .env.  
On application startup, if the specified database file is empty, the system will automatically:
- Initialize all required tables
- Populate the database with mock data for testing

This ensures a fresh clone of the project can be set up and run without any manual database configuration.  
Note: An empty SQLite database file must exist at the path specified in .env. The application will handle schema creation and data seeding automatically.


## Data Architecture
The system is built on a normalized relational schema that models both academic structures and student planning workflows.

<img src="screenshots/schema_1.png" alt="1st screenshot of schema" width=500>
<img src="screenshots/schema_2.png" alt="2nd screenshot of schema" width=500>

### Key Design Highlights
- Core academic entities (courses, departments, instructors)
- Enrollment and waitlist modeling
- Prerequisite and corequisite relationships
- Many-to-many instructor mapping
- Extensible structure for intelligent scheduling and planning


## 🎯 Example Use Case
A student selects 4 technical courses
The system:
- Flags high workload
- Estimates elevated burnout risk
- Suggests replacing one course
- Explains the tradeoff (e.g., "Replacing CS 143 with CS 122 reduces workload by 25% and improves expected performance")


## 🚧 Project Status
This project is under active development.  
Current Phase: Core system complete. Intelligence layer in progress. (Phase 2)  
Phase 1: Course planning system  
Phase 2: Workload modeling & risk detection  
Phase 3: Recommendation engine & schedule optimization  
Phase 4: Explainability & user insights  


## 🚀 Future Enhancements
- Personalized course recommendations based on academic goals
- Workload estimation and burnout risk analysis
- Schedule optimization and alternative course suggestions
- Time allocation and study planning support
- Historical performance tracking
- Advanced scheduling constraints (e.g., time conflicts, instructor preferences)


## 🧠 What I Learned
- Designing systems with real-world constraints
- Building relational data models for complex workflows
- Balancing backend logic with user experience
- Thinking beyond functionality toward decision-support systems


## 📷 Demo / Screenshots
<img src="screenshots/course-schedule.png" alt="Course Schedule page" width=500> <img src="screenshots/waitlist.png" alt="Waitlist page" width=500>
<img src="screenshots/filter-courses.png" alt="Filter Courses page" width=500> <img src="screenshots/course-listing.png" alt="Course Listing page" width=500>
