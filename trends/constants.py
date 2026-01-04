

# Access Levels
class AccessLevel:
    PUBLIC = 'public'
    PRIVATE = 'private'
    INSTITUTIONAL = 'institutional'
    
    ACCESS_LEVEL_CHOICES = [
        (PUBLIC, 'Public'),
        (PRIVATE, 'Private'),
        (INSTITUTIONAL, 'Institutional'),
    ]

# System Types
class SystemType:
    PRE_SCHOOL = 'pre_school'
    PRIMARY = 'primary'
    SECONDARY = 'secondary'
    VOCATIONAL = 'vocational'
    UNIVERSITY = 'university'
    OTHER = 'other'
    
    CHOICES = [
        (PRE_SCHOOL, 'Pre-School'),
        (PRIMARY, 'Primary School'),
        (SECONDARY, 'Secondary School'),
        (VOCATIONAL, 'Vocational Training'),
        (UNIVERSITY, 'University'),
        (OTHER, 'Other'),
    ]

# Level Types
class LevelType:
    GRADE = 'grade'
    YEAR = 'year'
    STAGE = 'stage'
    FORM = 'form'
    PROGRAM = 'program'
    COURSE = 'course'
    SEMESTER = 'semester'
    
    CHOICES = [
        (GRADE, 'Grade'),
        (YEAR, 'Year'),
        (STAGE, 'Stage'),
        (FORM, 'Form'),
        (PROGRAM, 'Degree Program'),
        (COURSE, 'Course'),
        (SEMESTER, 'Semester'),
    ]
    
# trends/constants.py
# Institution Types
class InstitutionType:
    EDUCATIONAL = 'educational'
    MEDICAL = 'medical'
    CORPORATE = 'corporate'
    GOVERNMENT = 'government'
    RELIGIOUS = 'religious'
    COMMUNITY = 'community'
    OTHER = 'other'
    
    CHOICES = [
        (EDUCATIONAL, 'Educational Institution'),
        (MEDICAL, 'Medical Institution'),
        (CORPORATE, 'Corporate Organization'),
        (GOVERNMENT, 'Government Agency'),
        (RELIGIOUS, 'Religious Organization'),
        (COMMUNITY, 'Community Organization'),
        (OTHER, 'Other'),
    ]

# trends/constants.py - Update SpaceType
class SpaceType:
    STUDY = 'study'
    INTERVIEW = 'interview'
    MEETING = 'meeting'
    
    CHOICES = [
        (STUDY, 'Study Space'),
        (INTERVIEW, 'Interview Space'),
        (MEETING, 'Meeting Space'),
    ]
    
    DESCRIPTIONS = {
        STUDY: 'Create a collaborative learning environment for academic subjects, exam preparation, group projects, and homework help',
        INTERVIEW: 'Practice and prepare for interviews, mock interviews, career preparation, resume reviews, and job search strategies',
        MEETING: 'Collaborate and connect for group discussions, project planning, study group meetings, and academic conferences',
    }

# Trend Types (Schedules/Timetables)
class TrendType:
    CLASS_SCHEDULE = 'class_schedule'
    SURGERY_SCHEDULE = 'surgery_schedule'
    MEETING_SCHEDULE = 'meeting_schedule'
    WORK_SHIFT = 'work_shift'
    APPOINTMENT = 'appointment'
    EVENT = 'event'
    
    CHOICES = [
        (CLASS_SCHEDULE, 'Class Schedule'),
        (SURGERY_SCHEDULE, 'Surgery Schedule'),
        (MEETING_SCHEDULE, 'Meeting Schedule'),
        (WORK_SHIFT, 'Work Shift'),
        (APPOINTMENT, 'Appointment'),
        (EVENT, 'Event'),
    ]

# User Roles (Updated)
class UserRole:
    PARTICIPANT = 'participant'
    SETTER = 'setter'
    ADMIN = 'admin'
    
    # Institution-specific roles
    INSTITUTION_ADMIN = 'institution_admin'
    INSTITUTION_MANAGER = 'institution_manager'
    INSTITUTION_USER = 'institution_user'
    
    # Type-specific roles
    TEACHER = 'teacher'
    STUDENT = 'student'
    DOCTOR = 'doctor'
    NURSE = 'nurse'
    STAFF = 'staff'
    
    CHOICES = [
        (PARTICIPANT, 'Participant'),
        (SETTER, 'Setter'),
        (ADMIN, 'Admin'),
        (INSTITUTION_ADMIN, 'Institution Admin'),
        (INSTITUTION_MANAGER, 'Institution Manager'),
        (INSTITUTION_USER, 'Institution User'),
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (DOCTOR, 'Doctor'),
        (NURSE, 'Nurse'),
        (STAFF, 'Staff'),
    ]    