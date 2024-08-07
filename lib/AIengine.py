#!/bin/python3

## CHIP'S OCEAN GAME (COG) AI ENGINE
##
## Functions related to interfacing with OpenAI


# IMPORTS AND CONSTANTS
import openai
import re
import logging
from datetime import datetime
from base64 import b64decode

from lib.configManager import loadConfig

confFile = "./etc/main.conf"


# FUNCTIONS
def getWeirdness(wVal):
    # Maps a weirdness value to a descriptive word. Takes in the weirdness
    # value (int) as input, returns the word as a string.
    wMap = { 1  : "mundane", 6  : "distinctive", 
             2  : "typical", 7  : "eccentric",
             3  : "normal",  8  : "weird",
             4  : "average", 9  : "alien",
             5  : "unique",  10 : "inexplicable" }
    try:
        wWord = wMap[wVal]
    except:
        wWord = 'unremarkable'
    return wWord

def getSize(size):
    # Takes the size of a POI (in terms of minutes required to explore) and
    # returns a rough descriptive value.
    if 0 < size <= 15:
        return "small"
    elif 15 < size <= 30:
        return "medium"
    elif 30 < size <= 45:
        return "large"
    elif 45 < size <= 60:
        return "huge"
    else:
        return "unknown size"

def getPOIdescription(pProps, size):
    # Asks GPT3 to generate a short description of a given POI. Takes the POI's
    # properties as input, returns the description as a string.
    weirdword = getWeirdness(pProps['weirdness'])
    sizeWord  = getSize(size)

    tPrompt = f"The crew has found a {sizeWord}, {pProps['adj']} {pProps['type']}."
    tPrompt = f"{tPrompt} The {pProps['type']} is {weirdword}. In five sentences"
    tPrompt = f"{tPrompt} or less, write a description of the {pProps['type']},"
    tPrompt = f"{tPrompt} along with mentioning flora and fauna that might be"
    tPrompt = f"{tPrompt} present."

    try:
        response = openai.Completion.create(
            model = "text-davinci-003",
            prompt = tPrompt,
            temperature = 0.9,
            max_tokens = 256)
        return response['choices'][0]['text']
    except:
        return f"{pProps['name']} is a {sizeWord}, {pProps['adj']} {pProps['type']}."

def getObjectDescription(type, pProps, story=""):
    # Asks GPT3 to generate a short description of a discovered obect. Takes
    # the type of object (artifact, tech, plant, animal) as well as the 
    # properties of the POI where it was found, returns description as a string.
    # If the artifact is story-relevant, then the previous entry of the story
    # will also be passed.
    tPrompt = ""
    wWord = getWeirdness(pProps['weirdness'])

    if story != "":
        tPrompt = f"Previously, {story}\n\n And now..."

    if type == "artifact":
        tPrompt = f"{tPrompt}The crew has discovered an ancient artifact at "
        tPrompt = f"{tPrompt}{pProps['name']}. The artifact is {wWord}. Write "
        tPrompt = f"{tPrompt}a paragraph describing in detail what the artifact "
        tPrompt = f"{tPrompt}looks like. "
    elif type == "tech":
        tPrompt = f"{tPrompt}The crew has discovered some kind of technological "
        tPrompt = f"{tPrompt}device at {pProps['name']}. The device is {wWord}. "
        tPrompt = f"{tPrompt}Write a paragraph describing in detail what the "
        tPrompt = f"{tPrompt}device looks like."
    elif type == "plant":
        tPrompt = f"{tPrompt}The crew has discovered what appears to be some "
        tPrompt = f"{tPrompt}kind of flora at {pProps['name']}. The plant is "
        tPrompt = f"{tPrompt}{wWord}. Write a paragraph describing in detail "
        tPrompt = f"{tPrompt}what the plant looks like."
    elif type == "animal":
        tPrompt = f"{tPrompt}The crew has discovered a {wWord} animal at "
        tPrompt = f"{tPrompt}{pProps['name']}. Describe in detail what the "
        tPrompt = f"{tPrompt}beast looks like."
    else:
        tPrompt = f"{tPrompt}The {type} found at {pProps['name']} defies "
        tPrompt = f"{tPrompt}description, other than to say it's {wWord}. "
        tPrompt = f"{tPrompt}Write a paragraph describing what it looks like. "
    
    try:
        response = openai.Completion.create(
            model = "text-davinci-003",
            prompt = tPrompt,
            temperature = 0.9,
            max_tokens = 256)
        return response['choices'][0]['text']
    except:
        return f"The crew found a {type} at {pProps['name']}, and it's very {wWord}."

def getName(thing):
    # Queries GPT3 to come up with a suitable name for <thing>. Returns a
    # string containing the name. 
    if thing in [ 'Chief Engineer',
                  'Chief Science Officer',
                  'Junior Engineer',
                  'Junior Scientist' ]:
        tPrompt = f"Come up with a first and last name for a {thing}. The name should be a normal English name."
    else:        
        tPrompt = f"Choose a unique name for a {thing} located in the middle of the ocean."

    try:
        response = openai.Completion.create(
            model = "text-davinci-003",
            prompt=tPrompt,
            temperature=0.9)
    except:
        return f"Unknown {thing}".title()
    
    name = response['choices'][0]['text']
    name = re.sub(r'[^\w\s]', '', name).replace('\n', '').replace('\r', '')

    if thing == 'ship':
        return f"the {name.title()}"
    return name.title()

def getImage(tprompt, tag):
    # Feeds a supplied prompt to Dall-E 2 and saves the resulting image.
    # Returns the filename of the image (constructed partially from <tag>)
    while len(tprompt) > 4000:
        tprompt = tprompt[:-4]

    aPrompt = f"A photograph of the following item:\n{tprompt}\n"
    aPrompt = f"{aPrompt}The image MUST look like a realistic photograph from a camera."

    try:
        response = openai.Image.create(prompt=aPrompt, response_format="b64_json")
    except Exception as e:
        logging.info(f"Failed to generate image: {e}")
        return conf['err_noimage']
    
    imageData = b64decode(response["data"][0]["b64_json"])

    cTime = datetime.now()
    dStamp = cTime.strftime("%Y%m%d-%H%M")
    filename = f"{dStamp}_{tag}_camimage.png"

    with open(f"./{conf['savedir']}/images/{filename}", "wb") as image:
        image.write(imageData)
        logging.info(f"Saved image file at: {filename}")
    
    return filename

def getPersonalLog(name, ship, role="", event="", prevlog=""):
    tPrompt = ""

    if prevlog != "":
        tPrompt = f"{tPrompt}{name}'s previous log entry was the following:\n"
        tPrompt = f"{tPrompt}{prevlog}\n"
    
    if event != "":
        tPrompt = f"{tPrompt}From the perspective of {role} {name}, write a "
        tPrompt = f"{tPrompt}personal log describing the recent {event}."
        tPrompt = f"{tPrompt}The log does NOT need to have a date at the beginning."
    else:
        tPrompt = f"{tPrompt}From the perspective of {role} {name}, write a "
        tPrompt = f"{tPrompt}personal log about life aboard the ocean-faring vessel {ship}. "
        tPrompt = f"{tPrompt}The log does NOT need to have a date at the beginning. Do NOT "
        tPrompt = f"{tPrompt}make any references to specific times or locations. Do not "
        tPrompt = f"{tPrompt}mention how long the mission is."
    
    if prevlog != "":
        tPrompt = f"{tPrompt}\nThe log should continue from the previous log to form an "
        tPrompt = f"{tPrompt}overall story."
    
    try:
        response = openai.Completion.create(
            model = "text-davinci-003",
            prompt = tPrompt,
            temperature = 0.9,
            max_tokens = 256)
        return response['choices'][0]['text']
    except:
        return ""


# INITIALIZATION
conf = loadConfig(confFile)
openai.api_key = conf['api_openai']
# These logger lines ensure that the openAI module doesn't screw with COG's
# default logger configuration.
openai_logger = logging.getLogger('openai')
openai_logger.setLevel(logging.CRITICAL)   
#openai_logger.addHandler(logging.FileHandler(conf['logfile'], mode='a'))
openai_logger.addHandler(logging.NullHandler())

# UNIT TESTS
if __name__ == "__main__":
    # Test getImage()
    fname = getImage("A Test Pattern", "TEST")
    print(f"Your test image can be found at {fname}")

    # Test getName()
    print(getName("sailing ship"))