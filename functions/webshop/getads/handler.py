# functions/webshop/getads/handler.py

import random

adsarray = [
    {"redirect_url": "https://www.example1.com", "image_url": "https://www.example1.com/image1.jpg", "text": "Are you tired of debugging your code? Try our new 'Debugging-Free' programming language!"},
    {"redirect_url": "https://www.example2.com", "image_url": "https://www.example2.com/image2.jpg", "text": "Want to impress your colleagues? Learn the latest and greatest programming language: Brainfuck!"},
    {"redirect_url": "https://www.example3.com", "image_url": "https://www.example3.com/image3.jpg", "text": "Tired of staring at a blank screen? Try our 'Code-Generating' software and start coding in minutes!"},
    {"redirect_url": "https://www.example4.com", "image_url": "https://www.example4.com/image4.jpg", "text": "Want to be a real hacker? Learn COBOL!"},
    {"redirect_url": "https://www.example5.com", "image_url": "https://www.example5.com/image5.jpg", "text": "Are you a real programmer? Prove it by coding in Assembly language!"},
    {"redirect_url": "https://www.example6.com", "image_url": "https://www.example6.com/image6.jpg", "text": "Want to be a real man? Code in C!"},
    {"redirect_url": "https://www.example7.com", "image_url": "https://www.example7.com/image7.jpg", "text": "Want to be a real woman? Code in Python!"},
    {"redirect_url": "https://www.example8.com", "image_url": "https://www.example8.com/image8.jpg", "text": "Want to be a real hacker? Learn COBOL!"},
    {"redirect_url": "https://www.example9.com", "image_url": "https://www.example9.com/image9.jpg", "text": "Want to be a real developer? Learn Java!"},
    {"redirect_url": "https://www.example10.com", "image_url": "https://www.example10.com/image10.jpg", "text": "Want to be a real nerd? Learn LISP!"}
]

async def handler(event, context=None, call_function=None):
    print("[get_ads] Eingabe:", event)
    return random.sample(adsarray, 2)


