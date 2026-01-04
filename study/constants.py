# study/constants.py
class ResourceType:
    TEXT = 'text'
    AUDIO = 'audio'
    VIDEO = 'video'
    PDF = 'pdf'
    
    CHOICES = [
        (TEXT, 'Text Notes'),
        (AUDIO, 'Audio Recording'),
        (VIDEO, 'Video Recording'),
        (PDF, 'PDF Document'),
    ]

class UIDPrefix:
    RESOURCE = 'res'
    CATEGORY = 'cat'
    BOOKMARK = 'bmk'