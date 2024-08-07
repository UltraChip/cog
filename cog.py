#!/bin/python3

## CHIP'S OCEAN GAME (COG) MAIN SCRIPT
##
## The primary script driving COG.


# IMPORTS AND CONSTANTS
import praw
import os
import logging
import random
import json
import time
from time import sleep, perf_counter
from math import floor

import lib.AIengine as ai
import lib.navigation as nav
import lib.worldgen as wg
import lib.configManager as cm
import lib.displayEngine as display
import lib.dbServices as dbs

confFile = "etc/main.conf"


# FUNCTIONS
def sensorSweep(shipState):
    # Polls ship's sensors to find new POIs and add them to TO_EXPLORE.
    contacts = []
    newconts = []
    shipLoc = (shipState['shipX'], shipState['shipY'])

    for sensor in ['radar','sonar']:
        range = nav.computeEffectiveRange(shipState[f"range_{sensor}"], shipState[f"mod_{sensor}"])
        clist = wg.sensorSweep(shipLoc, range, sensor)
        for c in clist:
            contacts.append(c)

    # Check if a detected contact is already in the DB (both TO_EXPLORE and POI)
    for contact in contacts:
        if dbs.lookupEID(contact)==None and dbs.lookupPID(contact)==None:
            newconts.append(contact)

    dbs.writeContacts(newconts)
    return

def magicCoin(prob):
    # Randomly returns True according to probability <prob>. If prob is a
    # string then it is parsed for keywords that map to pre-set probabilities,
    # such as average chance of hit once per day, once per month, etc. If
    # prob is an int then it will be taken as a direct value.
    heads = False
    if isinstance(prob, str):
        # Note: These numbers are based on the amount of 5-second ticks in a
        #       given period. e.g., 'daily' is the number of 5s ticks per day.
        pTable = { "daily"   : 17280,  "bidaily"   : 34560,
                   "weekly"  : 120960, "biweekly"  : 241920,
                   "monthly" : 518400, "bimonthly" : 1036800 }
        p = pTable[prob.lower()]
    else:
        p = prob

    if random.randrange(p) == 1:
        heads = True
    return heads

def boldlyGo(shipState):
    # In certain situations, the captain will decide to "Boldly Go", a.k.a.
    # "choose a random heading and sail off in to the distance." This helps
    # ensure that the ship doesn't just loiter in the same general area forever
    shipLoc = (shipState['shipX'], shipState['shipY'])
    # 240-1680 chosen because that translates to between 1-7 day's journey at 
    # stock speed.
    distance = random.uniform(240, 1680)
    heading  = random.uniform(0, 360)

    x, y = nav.computeTravel(shipLoc, heading, distance)
    targetLoc = getSimpleCoords(x, y)
    dbs.updateBold(targetLoc)
    shipState['trackID'] = 1
    logging.info(f"Captain has decided to Boldly Go to distant coordinates {targetLoc}!")
    return shipState

def crewActions(shipState):
    # Decision-making for the crew to be performed on each tick. 
    shipLoc = (shipState['shipX'], shipState['shipY'])  
    maxSPD = shipState['max_spd']  
    random.seed(wg.makeGridSeed(shipLoc[0], shipLoc[1]))
    # Captain:
    #    Check if ship is in dire need of something and needs to divert course.
    components = ['hull', 'engine', 'lab', 'bridge']
    needRepair = False
    needProvs  = False
    pid = None
    if shipState['cargo_fuel']/shipState['fuel_cap'] < 0.333:
        estFuelCost = (shipState['fuel_cap']-shipState['cargo_fuel'])*2
        if shipState['money'] >= estFuelCost:
            fSrc = dbs.dumpType('offshore platform')
            fSrc = fSrc + dbs.dumpType('deposit')
            pid = nav.getClosest(shipLoc, fSrc)
        else:
            pid = nav.getClosest(shipLoc, dbs.dumpType('deposit'))
    if shipState['cargo_food'] <= 105 or shipState['cargo_water'] <= 7000:
        needProvs = True
    for component in components:
        if shipState[f'health_{component}'] <= 25:
            needRepair = True
    if needProvs or needRepair:
        pid = nav.getClosest(shipLoc, dbs.dumpType('offshore platform'))
    if pid:
        if shipState['trackID'] != dbs.lookupEID((pid[1][0], pid[1][1])):
            dbs.writeContacts([pid[1]])
            shipState['trackID'] = dbs.lookupEID((pid[1][0], pid[1][1]))
            logging.info(f"BRIDGE: Ship in jeopardy! Captain is setting course for EID:{shipState['trackID']} in hopes of getting repairs and/or supplies.")
    #    Otherwise, choose a track if one isn't already set.
    if shipState['trackID'] == -1:
        if magicCoin(10): 
            shipState = boldlyGo(shipState)
        else:
            toExplore = dbs.dumpAllContacts()
            while shipState['trackID'] == -1:
                candidateContact = random.choice(toExplore)
                # Limiting range to 480 (2 day's journey @ stock speed) helps
                # ensure the captain doesn't choose a contact clear on the
                # other side of the world or anything like that.
                if nav.computeRange(shipLoc, candidateContact[1]) <= 480:
                    shipState['trackID'] = candidateContact[0]
            logging.info(f"BRIDGE: Captain has set course for unexplored contact EID:{shipState['trackID']}.")
    #    Set course and speed
    contact = dbs.lookupContact(shipState['trackID'])
    shipState['hdg'] = nav.computeBearing(shipLoc, contact)
    shipState['spd'] = maxSPD
    #    Chance of writing a personal log
    if magicCoin("bidaily"):
        writeOfficialLog(shipState, 'co')
        logging.info(f"{shipState['co']['fTitle']} {shipState['co']['name']} has written a personal log.")
    
    # Chief Engineer:
    # Repair/maintain components in accordance with component priorities.
    if shipState['cheng']['health'] > 25:
        priorities = ['engine', 'bridge', 'lab', 'dinghy', 'sub']
        for component in priorities:
            if 0 < shipState[f'health_{component}'] <= 75:
                rsrc = 'iron' if component in ['engine','dinghy','sub'] else 'silicon'
                if shipState[f'cargo_{rsrc}'] > 0:
                    shipState[f'cargo_{rsrc}'] -= 1
                    shipState[f'health_{component}'] += 1
                    break
    if magicCoin("bidaily") and shipState['cheng']['name'] != "VACANT":
        writeOfficialLog(shipState, 'cheng')
        logging.info(f"{shipState['cheng']['fTitle']} {shipState['cheng']['name']} has written a personal log.")
    
    # Chief Science Officer:
    # Research stuff. If Stuff gets fully researched then reward accordingly.
    if shipState['cso']['health'] > 25 and shipState['health_lab'] > 25:
        toResearch = []
        if shipState['to_analyze_tech'] > 0:
            toResearch.append('tech')
        if shipState['to_analyze_artifact'] > 0:
            toResearch.append('artifact')
        if len(toResearch) > 0:
            thing = random.choice(toResearch)
            if shipState['health_lab'] > 75:
                shipState[f'lab_count_{thing}'] -= 1
            else:
                shipState[f'lab_count_{thing}'] -= 0.5
            if shipState[f'lab_count_{thing}'] <= 0:
                shipState = rewardResearch(shipState, thing)
    if magicCoin("bidaily") and shipState['cso']['name'] != "VACANT":
        writeOfficialLog(shipState, 'cso')
        logging.info(f"{shipState['cso']['fTitle']} {shipState['cso']['name']} has written a personal log.")
    
    # Junior Engineer
    # Pretty similar to Chief Engineer, except Jr. Eng has time to repair
    # stuff all the way up to 90%
    if shipState['eng']['health'] > 25:
        priorities = ['engine', 'bridge', 'lab', 'dinghy', 'sub']
        for component in priorities:
            if 0 < shipState[f'health_{component}'] <= 90:
                rsrc = 'iron' if component in ['engine','dinghy','sub'] else 'silicon'
                if shipState[f'cargo_{rsrc}'] > 0:
                    shipState[f'cargo_{rsrc}'] -= 1
                    shipState[f'health_{component}'] += 1
                    break
    if magicCoin("bidaily") and shipState['eng']['name'] != "VACANT":
        writeOfficialLog(shipState, 'eng')
        logging.info(f"{shipState['eng']['fTitle']} {shipState['eng']['name']} has written a personal log.")
    
    # Junior Scientist
    # Similar to Chief Science Officer, except they aren't able to finalize
    # research and claim rewards.
    if shipState['sci']['health'] > 25 and shipState['health_lab'] > 25:
        toResearch = []
        if shipState['to_analyze_tech'] > 0:
            toResearch.append('tech')
        if shipState['to_analyze_artifact'] > 0:
            toResearch.append('artifact')
        if len(toResearch) > 0:
            thing = random.choice(toResearch)
            if shipState['health_lab'] > 75:
                shipState[f'lab_count_{thing}'] -= 1
            else:
                shipState[f'lab_count_{thing}'] -= 0.5
    if magicCoin("bidaily") and shipState['sci']['name'] != "VACANT":
        writeOfficialLog(shipState, 'sci')
        logging.info(f"{shipState['sci']['fTitle']} {shipState['sci']['name']} has written a personal log.")
    return shipState

def rewardResearch(shipState, thing):
    # If the lab has completed research, this function will process their
    # reward. Also resets research counters. Returns shipState.
    if thing == 'artifact':
        reward = random.randrange(30000,50000)
        shipState['money'] += reward
        shipState['to_analyze_artifact'] -= 1
        shipState['lab_count_artifact'] = shipState['lab_base']
        logging.info(f"LAB: Transmitted completed artifact research, received ${reward} reward!")
    else:  # thing == 'tech'
        reward = random.randrange(5000,10000)
        shipState['money'] += reward
        component = random.choice([ 'max_spd',   'fuel_eff', 'lab_base',
                                    'mod_radar', 'mod_sonar' ])
        
        if component == 'max_spd':
            shipState[component] += 1
            shipState['cargo_iron'] -= 10
            if shipState['cargo_iron'] < 0:
                shipState['cargo_iron'] = 0
            msg = f"increased max speed by 1 knot!"
        if component in ['mod_radar', 'mod_sonar']:
            shipState[component] += random.randrange(2,10)
            shipState['cargo_silicon'] -= 10
            if shipState['cargo_silicon'] < 0:
                shipState['cargo_silicon'] = 0
            msg = f"boosted {component[4:]}'s range to {shipState[component]}% above baseline!"
        if component == 'fuel_eff':
            shipState['fuel_eff'] -= random.uniform(0,1)
            shipState['cargo_iron'] -= 10
            if shipState['cargo_iron'] < 0:
                shipState['cargo_iron'] = 0
            msg = f"improved fuel efficiency to {shipState['fuel_eff']} liters per NM!"
            if shipState['fuel_eff'] < 1:
                shipState['fuel_eff'] = 1
                msg = f"attempted to improve fuel efficiency, but already at optimal."
        if component == 'lab_base':
            ptsOff = round(shipState['lab_base']*random.uniform(0.01, 0.05))
            shipState['lab_base'] -= ptsOff
            shipState['cargo_silicon'] -= 10
            if shipState['cargo_silicon'] < 0:
                shipState['cargo_silicon'] = 0
            msg = f"reduced lab research time by {ptsOff} points!"
        
        shipState['to_analyze_tech'] -= 1
        shipState['lab_count_tech'] = shipState['lab_base']
        logging.info(f"LAB: Completed technology research, received ${reward} and {msg}")
    return shipState

def makeSaveFile(filename):
    # Creates and initializes the ship state save file if it doesn't already
    # exist. Takes in the filename as input. Does not return any output.
    dirs = [ "images", 
             "logs/auto",
             "logs/cheng",
             "logs/co", 
             "logs/cso", 
             "logs/eng",
             "logs/sci" ]
    for dir in dirs:
        os.makedirs(f"{conf['savedir']}/{dir}", mode=0o660, exist_ok=True)

    shipState = cm.loadConfig(f"./etc/template.save")
    print(f"\nNo ship currently on file!")

    sName = input("What is the vessel's name? ").title()
    shipState['name'] = f"ESV {sName}"
    print(f"\nCommissioned {conf['hull']} : the {shipState['name']}\n")

    shipState['co']['name']    = input("Enter the Captain's name:               ").title()
    shipState['cheng']['name'] = input("Enter the Chief Engineer's name:        ").title()
    shipState['cso']['name']   = input("Enter the Chief Science Officer's name: ").title()
    shipState['eng']['name']   = input("Enter the engineer's name:              ").title()
    shipState['sci']['name']   = input("Enter the scientist's name:             ").title()

    cm.writeConfig(shipState, filename)
    logging.info("Created new save.")
    return

def countPlayers(shipState):
    # Count the number of living players (crewmembers). Returns as an int.
    count = 0
    players = [ "co", "cheng", "cso", "eng", "sci" ]
    for player in players:
        if shipState[player]['name'] != "VACANT":
            count +=1
    return count

def updateShipState(shipState, t):
    # Updates vital stats for ship & crew, meant to run each game tick.
    engineDPS = 0.000004823  # Damage per second to lose 25HP in two months
    crewHPS   = 0.000289352  # Heal per second to gain 50 HP in two days
    doDailies = False        # Flag to determine if daily calcs are performed.

    # Update ship clock (day & timestamp)
    tS  = shipState['tStamp']
    d   = shipState['day']
    tS += t
    if tS >= 86400:
        d += 1
        doDailies = True
        tS = tS - 86400
    shipState['tStamp'] = tS
    shipState['day']    = d

    # Calculate new ship location & update odometer
    speed     = shipState['spd']
    shipLoc   = (shipState['shipX'], shipState['shipY'])
    heading   = shipState['hdg']
    perSecond = (speed/60)/60
    distance  = perSecond*t
    newLoc    = nav.computeTravel(shipLoc, heading, distance)
    shipState['shipX']     = newLoc[0]
    shipState['shipY']     = newLoc[1]
    shipState['odometer'] += distance

    # Decrement Ship's Resources
    engineH = shipState['health_engine']
    fuel    = shipState['cargo_fuel']
    fuelE   = shipState['fuel_eff']
    food    = shipState['cargo_food']
    water   = shipState['cargo_water']

    engineH -= engineDPS*t
    engineH  = 0 if engineH < 0 else engineH
    fuel    -= fuelE*distance
    fuel     = 0 if fuel < 0 else fuel
    if doDailies:
        numPlayers = countPlayers(shipState)
        food      -= 3*numPlayers
        food       = 0 if food < 0 else food
        water     -= 200*numPlayers
        water      = 0 if water < 0 else water
    
    shipState['health_engine'] = engineH
    shipState['cargo_fuel']    = fuel
    shipState['cargo_food']    = food
    shipState['cargo_water']   = water

    # Update player stats
    crew = ['co', 'cheng', 'cso', 'eng', 'sci']
    for person in crew:
        if shipState[person]['name'] != "VACANT":
            h  = shipState[person]['health']
            if food > 0 and water > 0:
                h += crewHPS*t
            else:
                if food <= 0:
                    h -= crewHPS*t
                if water <= 0:
                    h -= crewHPS*t*2
            h  = 100 if h > 100 else h
            shipState[person]['health'] = h
    return shipState

def getSimpleCoords(x,y):
    # Takes a set of coordinates and floors them in to ints to provide a
    # general grid square location. Takes in X and Y coordinate values, returns
    # integer X,Y values as a tuple.
    x = int(round(x))
    y = int(round(y))
    return (x, y)

def canExplore(shipState, contact):
    # Small function to determine if ship is ready and able to explore a
    # provided contact. Returns True if ready, False if not.
    if shipState['health_dinghy'] > 0 and contact[2] == "U":
        return True
    elif shipState['health_sub'] > 0 and contact[2] == "L":
        return True
    else:
        return False

def doze(mins):
    # Sleeps for a specified number of minutes, assuming "quickExplore" flag
    # is disabled. Returns no output.
    if not shipState['quikExplore']:
        sleep(60*mins)
    return

def atPOI(shipState, contact):
    # Main event handler for when ship is at a POI. Takes in contact (tuple),
    # returns shipState. 
    shipState['spd'] = 0
    random.seed(wg.makeGridSeed(shipState['shipX'], shipState['shipY']))
    images = []
    pProps = {}
    size = random.randrange(1, 60)
    picTypes = ["island", "derelict", "wreck", "coral", "underwater cave"]
    picLife = ["island", "wreck", "coral", "underwater cave"]
    display.updateDisplay(shipState, "Anchoring...")

    pid = dbs.lookupPID(contact)
    if pid is not None:
        POIdata = dbs.loadPOI(pid)
        pProps['type']      = POIdata[0]
        pProps['name']      = POIdata[1]
        pProps['adj']       = POIdata[2]
        pProps['weirdness'] = POIdata[3]
        desc                = POIdata[4]
        images = json.loads(POIdata[5])
        logging.info(f"Arrived at {pProps['name']}")
    else:
        pProps = wg.getPOI(contact)
        desc = ai.getPOIdescription(pProps, size)
        logging.info(f"Discovered new {pProps['type']} and named it {pProps['name']}")
    dbs.deleteEID(shipState['trackID'])
    shipState['trackID'] = -1

    ## Generate initial pictures
    if pProps['type'] in picTypes:
        tag = f"{shipState['day']}-{shipState['tStamp']}_{contact[0]}-{contact[1]}_{pProps['name']}"
        images.append(ai.getImage(desc, tag))
    
    ## Deploy explorers and wait for explore time (if applicable)
    if pProps['type'] in picTypes:
        awayPri = ['sci', 'eng', 'cso', 'cheng', 'co']
        awayTeam = []
        for role in awayPri:
            if shipState[role]['name'] != "VACANT" and shipState[role]['health'] > 75:
                awayTeam.append(role)
                logging.info(f"Adding {shipState[role]['fTitle']} {shipState[role]['name']} to away team")
            if len(awayTeam) >= 2:
                break
        if canExplore(shipState, contact):
            logging.info(f"Deploying away team to explore {pProps['name']}")
            random.seed(f"{conf['hull']}-{shipState['day']}-{shipState['tStamp']}")
            if pProps['type'] in ['island', 'derelict']:
                boat = 'dinghy'
            else:
                boat = 'sub'            
            display.updateDisplay(shipState, f"Away team deployed to {pProps['name']}")
            doze(size)
            if random.randrange(0, 100) < 10:  # Chance of boat damage
                damage = random.randrange(10, 100)
                shipState[f"health_{boat}"] -= damage
                logging.info(f"The {boat} took damage during the away mission! Health is at {shipState[f'health_{boat}']}")
                if shipState[f"health_{boat}"] <= 0:
                    shipState[f"health_{boat}"] = 0
                    for member in awayTeam:
                        crewDeath(shipState, member)
                    logging.info(f"The {boat} was destroyed during the mission - all hands lost.")
                    writeOfficialLog(shipState, 'co', f"loss of the away team while exploring {pProps['name']}")
            if random.randrange(0, 100) < 10: # Chance of personal injury
                damage = random.randrange(10, 100)
                pickCrew = awayTeam[random.randint(0,1)]
                shipState[pickCrew]['health'] = shipState[pickCrew]['health'] - damage
                logging.info(f"{shipState[pickCrew]['name']} got injured during the away mission! Health is at {shipState[pickCrew]['health']}")
                if shipState[pickCrew]['health'] <= 0:
                    fname = f"{shipState[pickCrew]['fTitle']} {shipState[pickCrew]['name']}"
                    shipState[pickCrew]['health'] = 0
                    crewDeath(shipState, pickCrew)
                    awayTeam.remove(pickCrew)
                    writeOfficialLog(shipState, awayTeam[0], f"lost crewmate {fname} to an injury while exploring {pProps['name']}")
                else:
                    fname = f"{shipState[pickCrew]['fTitle']} {shipState[pickCrew]['name']}"
                    writeOfficialLog(shipState, pickCrew, f"got injured while exploring {pProps['name']}")

            if shipState[f'health_{boat}'] >= 0:
                if pProps['type'] in picLife:
                    desc_fauna = ai.getObjectDescription("animal", pProps)
                    tag = f"{shipState['day']}-{shipState['tStamp']}_{contact[0]}-{contact[1]}_{pProps['name']}_fauna"
                    images.append(ai.getImage(desc_fauna,tag))
                    sleep(5)
                    desc_flora = ai.getObjectDescription("plant", pProps)
                    tag = f"{shipState['day']}-{shipState['tStamp']}_{contact[0]}-{contact[1]}_{pProps['name']}_flora"
                    images.append(ai.getImage(desc_flora,tag))
                    title = f"Away Team Report on Life Discovered at {pProps['name']}"
                    content = f"Excursion occurred on day {shipState['day']}.\n\n"
                    content = f"{content}Flora Discovered:\n    "
                    content = f"{content}{desc_flora}\n\nFauna Discovered:\n    {desc_fauna}"
                    postText(title, content)
                if "tech" in pProps['resources']:
                    desc_tech = ai.getObjectDescription("tech", pProps)
                    tag = f"{shipState['day']}-{shipState['tStamp']}_{contact[0]}-{contact[1]}_{pProps['name']}_tech"
                    images.append(ai.getImage(desc_tech,tag))
                    shipState['to_analyze_tech'] += 1
                    title = f"{shipState['cso']['fTitle']}'s Report on Recovered Technology Discovered at {pProps['name']}"
                    content = f"Excursion occurred on day {shipState['day']}.\n\n"
                    content = f"{content}{desc_tech}"
                    postText(title, content)
                if "artifact" in pProps['resources']:
                    desc_art = ai.getObjectDescription("artifact", pProps)
                    tag = f"{shipState['day']}-{shipState['tStamp']}_{contact[0]}-{contact[1]}_{pProps['name']}_artifact"
                    images.append(ai.getImage(desc_art,tag))
                    shipState['to_analyze_artifact'] += 1
                    title = f"{shipState['cso']['fTitle']}'s Report on Ancient Artifact Discovered at {pProps['name']}"
                    content = f"Excursion occurred on day {shipState['day']}.\n\n"
                    content = f"{content}{desc_art}"
                    postText(title, content)
                
                for rsource in pProps['resources']:
                    cargo = f"cargo_{rsource}"
                    bAmount = random.uniform(10,40)
                    if rsource in ['food', 'iron', 'silicon']:
                        amount = round(bAmount)
                    elif rsource in ['water', 'fuel']:
                        amount = round(50*bAmount)
                    else:
                        continue
                    shipState[cargo] += amount
                    logging.info(f"Away team brought back {amount} {rsource} from {pProps['name']}")
                if shipState['cargo_fuel'] > shipState['fuel_cap']:
                    shipState['cargo_fuel'] = shipState['fuel_cap']
                if shipState['cargo_water'] > 150000:
                    shipState['cargo_water'] = 150000

    if pProps['type'] == "deposit":
        display.updateDisplay(shipState, f"{shipState['name']} tapping underwater oil deposit")
        doze(size)
        oil = 100*size
        shipState['cargo_fuel'] += oil
        logging.info(f"Ship managed to drill {oil} liters of oil from the underwater deposit.")
        if shipState['cargo_fuel'] > shipState['fuel_cap']:
            shipState['cargo_fuel'] = shipState['fuel_cap']

    ## Buy stuff (if applicable)
    if pProps['type'] == "offshore platform":
        display.updateDisplay(shipState, f"Docked with {pProps['name']}")
        doze(size)
        roles = ['cheng', 'cso', 'eng', 'sci']  # Replace crew if neccessary
        price = 500
        for role in roles:
            if shipState[role]['name'] == "VACANT":
                if shipState['money'] >= price:
                    shipState[role]['name'] = ai.getName(shipState[role]['fTitle'])
                    shipState[role]['health'] = 100
                    shipState['money'] = shipState['money'] - price
                    logging.info(f"Ship has hired {shipState[role]['name']} to the role of {shipState[role]['fTitle']}")
        
        # Repair ship's components for $10 per health unit
        components = ['hull', 'engine', 'lab', 'bridge', 'dinghy', 'sub']
        price = 10
        for component in components:
            health = f"health_{component}"
            needed = 100 - shipState[health]
            if component == "hull" and needed > 0:
                needed += 100
            cost = round((needed * price), 2)
            if shipState['money'] >= price:
                shipState[health] = 100
                shipState['money'] = shipState['money'] - cost
                logging.info(f"{pProps['name']} repaired the {component} for ${cost}")
        shipState = buyStuff(shipState)
        writeOfficialLog(shipState, "co", f"visiting and trading with {pProps['name']}")
    
    if pProps['type'] == "ship":
        display.updateDisplay(shipState, f"Docked with {pProps['name']}, meeting & trading")
        doze(size)
        shipState = buyStuff(shipState)
        writeOfficialLog(shipState, 'co', f"visiting and trading with the crew of {pProps['name']}")

    ## Write to POI table and post images
    if pid is None:
        dbs.writePOI(contact, pProps, desc, images)
    else:
        dbs.updatePOI(pid, images)
    if images != []:
        postImages(f"Photographs from {pProps['name']}", images)

    return shipState

def buyStuff(shipState):
    # Buys resources when at a "shop" POI. Takes in and returns ShipState.
    resources = [ [ "fuel",  2, shipState['fuel_cap'] ],
                  [ "water", 2, 150000 ],
                  [ "food",  5, 2250 ] ]
    money = shipState['money']
    
    for resource in resources:
        rsource = f"cargo_{resource[0]}"
        price   = resource[1]
        cap     = resource[2]
        if shipState[rsource] < cap:
            needed = cap - shipState[rsource]
            cost = round((needed*price),2)
            if cost < money:
                money -= cost
                shipState[rsource] += needed
                logging.info(f"Purchased {needed} {resource[0]} for ${cost}")
    shipState['money'] = money

    return shipState

def writeOfficialLog(shipState, role, event=""):
    # Generate, record, and post a log from the perspective of a crew member.
    path = f"./{conf['savedir']}/logs/{role}"

    # Grab the most recent log for this person.
    if event == "":
        lognames = os.listdir(path)
        try:
            while lognames[-1][-16:] != "PERSONAL.shiplog":
                lognames.pop()            
            lastlog = lognames[-1]
            with open(f"{path}/{lastlog}", "r") as file:
                lastlogtext = file.read()
                logging.info(f"Previous personal log {lastlog} found.")
        except:
            lastlogtext = ""
    else:
        lastlogtext = ""
    
    # Build a file name for this log
    cTime = time.strftime("%Y%m%d-%H%M", time.localtime())
    gTime = f"{shipState['day']}-{shipState['tStamp']}"
    tag = "EVENT" if event != "" else "PERSONAL"
    filename = f"{cTime}_{gTime}_{role.upper()}_{tag}.shiplog"

    # Generate the log
    fTitle = shipState[role]['fTitle']
    logtext = f"{fTitle}'s Log, Day {shipState['day']}, Time {shipState['tStamp']}\n\n"
    footer = display.buildFooter(shipState) if event != "" else ""
    gentext = ai.getPersonalLog(shipState[role]['name'], shipState['name'], fTitle, event, lastlogtext)
    logtext = "" if gentext == "" else f"{logtext}{gentext}\n{footer}"

    # Write the log to disk & post it online
    if logtext != "":
        with open(f"{path}/{filename}", "w") as file:
            file.write(logtext)
        if event != "":
            title = f"{fTitle}'s Log: {event.title()}"
        else:
            title = f"{fTitle}'s Personal Log"
        postText(title, logtext)
    return

def writeAutoLog(shipState, tag, descText):
    # Prepare, record, and post a log from the perspective of the ship's
    # computer. Intended to be used for "emergency messages".
    path = f"./{conf['savedir']}/logs/auto"

    # Build a file name for the log
    cTime = time.strftime("$Y%m%d-%H%M", time.localtime())
    gTime = f"{shipState['day']}-{shipState['tStamp']}"
    filename = f"{cTime}_{gTime}_SHIPCOM_{tag}.shiplog"

    # Put the log together and write it to disk
    title = f"EMERGENCY AUTOMATED MESSAGE {conf['hull'].upper()} {shipState['name'].upper()}: {tag.upper()}"
    footer = display.buildFooter(shipState)
    logtext = f"{title}\n\n{descText}\n{footer}"
    with open(f"{path}/{filename}", "w") as file:
        file.write(logtext)    
    
    # Post to Reddit
    postText(title, f"{descText}\n{footer}")
    return 

def postText(title, text):
    # Posts the provided text online (namely Reddit, unless I expand to other)
    # platforms in the future). Takes in the title and text as input, returns 
    # nothing as output.
    try:
        sub.submit(title, text)
    except:
        try:
            sleep(5)  # If posting fails, wait 5 seconds and try again
            sub.submit(title, text)
        except:
            try:
                sleep(5)  # If still failing after the 3rd try, then give up
                sub.submit(title, text)
            except:
                logging.info("Tried posting text to Reddit, but couldn't.")
                pass
    return

def postImages(title, images):
    # Posts the provided images to Reddit as a "gallery" post. Takes in post
    # title and list of images as input, returns nothing as output. 
    gallery = []
    if images == []:
        logging.info(f"Was asked to post images, but wasn't given any. {images}")
        return
    
    # PRAW expects images to be presented as a list of dicts.
    for image in images:
        if image == "./etc/err_image.png":
            gallery.append({"image_path":image})
        else:
            fpath = f"./{conf['savedir']}/images/{image}"
            gallery.append({"image_path":fpath})
    
    try:
        sub.submit_gallery(title, gallery)
    except:
        try:
            sleep(5)
            sub.submit_gallery(title, gallery)
        except:
            try:
                sleep(5)
                sub.submit_gallery(title, gallery)
            except Exception as e:
                logging.info("Tried posting images to Reddit, but couldn't.")
                logging.info(e)
                logging.info(gallery)
                pass
    return

def crewDeath(shipState, role):
    # Handles the processing for death of a crew member. Takes in ship state &
    # crewmember's role, returns revised shipState.
    logging.info(f"{shipState[role]['fTitle']} {shipState[role]['name']} has died.")
    shipState[role]['name']   = "VACANT"
    shipState[role]['health'] = 0
    rotateCrew(shipState)
    return shipState

def shipDeath(shipState):
    shipState['spd']     = 0
    shipState['hdg']     = 0
    shipState['trackID'] = -1
    
    descText = f"Commanding Officer of {conf['hull']} {shipState['name']} has ordered all hands"
    descText = f"{descText} to abandon ship. {countPlayers(shipState)} crew were confirmed to have"
    descText = f"{descText} embarked on the lifeboat, which deployed at an approximate location of"
    descText = f"{descText} {getSimpleCoords(shipState['shipX'], shipState['shipY'])}. Immediate search and"
    descText = f"{descText} rescue of lifeboat requested. This is {shipState['name']}'s final transmission."

    writeAutoLog(shipState, 'abandoned ship', descText)
    logging.info("Ship has sunk!")
    killSim(shipState)
    return

def killSim(shipState):
    # Gracefully shuts down the program.
    savefile = f"./{conf['savedir']}/{conf['savename']}"
    cm.writeConfig(shipState, savefile)
    quit()
    return

def rotateCrew(shipState):
    # Maintains the ship's chain-of-command by promoting crew members
    # appropriately after a loss of crew. Takes in and returns shipState.
    if shipState['co']['health'] <= 0:
        shipState['co']['name'] = shipState['cheng']['name']
        shipState['co']['health'] = shipState['cheng']['health']
        shipState['cheng']['name']   = "VACANT"
        shipState['cheng']['health'] = 0

    if shipState['cheng']['health'] <= 0:
        shipState['cheng']['name'] = shipState['eng']['name']
        shipState['cheng']['health'] = shipState['eng']['health']
        shipState['eng']['name']   = "VACANT"
        shipState['eng']['health'] = 0
    
    if shipState['cso']['health'] <= 0:
        shipState['cso']['name'] = shipState['sci']['name']
        shipState['cso']['health'] = shipState['sci']['health']
        shipState['sci']['name']   = "VACANT"
        shipState['sci']['health'] = 0

    return shipState

def isEvent(shipState):
    # Determine if a special event is happening during the tick and, if it is,
    # then handle it. Receives and returns shipState (dictionary).
    random.seed(wg.makeGridSeed(shipState['shipX'], shipState['shipY']))
    eventHappened = False

    ## Determine If Ship Dead
    if shipState['health_hull'] <= 0:
        shipDeath()

    ## Determine If On POI
    track    = dbs.lookupContact(shipState['trackID'])
    shipLoc  = getSimpleCoords(shipState['shipX'], shipState['shipY'])
    trackLoc = getSimpleCoords(track[0], track[1]) if track != None else (99999,99999)
    if shipLoc == trackLoc:
        if shipState['trackID'] == 1:
            shipState['trackID'] = -1
            logging.info("BRIDGE: Ship has arrived at 'Boldly Go' coordinates, clearing track.")
        else:
            atPOI(shipState, track)
            eventHappened = True

    ## Random ship malfunction
    if magicCoin('biweekly'):
        component = random.choice(['engine', 'lab', 'bridge', 'dinghy', 'sub'])
        eventText = f"malfunction in the {component}"
        damage = round(shipState[f'health_{component}']*random.randrange(75)/100)
        shipState[f'health_{component}'] -= damage
        writeOfficialLog(shipState, 'cheng', eventText)
        logging.info(f"ENGINEERING: {component} has suffered a critical malfunction.")
        eventHappened = True

    ## Storm Event
    if magicCoin('weekly'):
        severe = 3 if magicCoin(10) else 1  # Set multiplier for if the storm
                                            # is severe.
        components = ['hull', 'lab', 'bridge', 'dinghy', 'sub']
        for component in components:
            health = shipState[f'health_{component}']
            damage = round(health*(random.randrange(25)/100)*severe)
            shipState[f'health_{component}'] -= damage
        if severe == 3:
            eventText = "sustained severe damage after encountering a maelstrom"
        else:
            eventText = "encountered a light storm while at sea"
        writeOfficialLog(shipState, 'co', eventText)
        logging.info(f"ENGINEERING: Encountered a storm at sea - multiple systems damaged.")
        eventHappened = True 

    ## Determine If Creature Attack
    if magicCoin('monthly'):
        tPrompt = """ A horrific sea creature attacking a research vessel. The 
                      picture is from the perspective of a camera mounted on the
                      ship's bridge. """
        images = [ ai.getImage(tPrompt, "creature-attack") ]
        hulldamage = floor(shipState['health_hull']*random.randrange(75)/100)
        shipState['health_hull'] -= hulldamage
        component = random.choice(['engine', 'lab', 'bridge', 'dinghy', 'sub'])
        cDamage = round(shipState[f'health_{component}']*random.randrange(50)/100)
        shipState[f'health_{component}'] -= cDamage
        postImages(f"Footage from the creature attack on day {shipState['day']}", images)
        sleep(5)
        eventText = "sustained damage when attacked by a large sea creature"
        writeOfficialLog(shipState, 'co', eventText)
        logging.info(f"LAB: Encountered a previously-unknown leviathan at sea.")
        eventHappened = True
    
    ## Determine If Random Illness
    if magicCoin('monthly'):
        role = random.choice(['co', 'cheng', 'cso', 'eng', 'sci'])
        sickness = round(shipState[role]['health']*random.randrange(80)/100)
        shipState[role]['health'] -= sickness
        eventText = f"illness of {shipState[role]['fTitle']} {shipState[role]['name']}."
        writeOfficialLog(shipState, 'cso', eventText)
        logging.info(f"LAB: {shipState[role]['fTitle']} {shipState[role]['name']} has fallen ill.")
        eventHappened = True 
    
    if eventHappened:
        display.updateDisplay(shipState, "Underway")
    return shipState

def finishTick(shipState):
    # Do the final calculations to determine the ship & crew's state at the end
    # of the tick after any events and crew actions that may have occurred.
    speed   = shipState['spd']
    hull    = shipState['health_hull']
    engine  = shipState['health_engine']
    contact = dbs.lookupContact(shipState['trackID'])
    pid     = dbs.lookupPID(contact) if contact is not None else None

    if hull <= 0:
        shipDeath(shipState)
    for crew in [ 'co', 'cheng', 'cso', 'eng', 'sci' ]:
        if shipState[crew]['health'] <= 0 and shipState[crew]['name'] != "VACANT":
            crewDeath(shipState, crew)

    avgDamage = (hull+engine)/2
    speed = speed*(avgDamage/100)
    if engine <= 0 or shipState['cargo_fuel'] <= 0:
        speed = 0
    speed = 3 if 0 <= speed < 3 else speed
    shipState['spd'] = speed

    if pid is not None:
        poiname = dbs.loadPOI(pid)[1]
        msg = f"Cruising towards {poiname}"
    else:
        if shipState['trackID'] == 1:
            msg = f"Boldly going to distant point {contact[0]}, {contact[1]}"
        elif shipState['trackID'] == -1:
            msg = f"Ship is preparing to get underway."
        else:
            subsurf = "surface" if contact[2] == "U" else "submerged"
            msg = f"Cruising towards unexplored {subsurf} contact at {contact[0]}, {contact[1]}"
    display.updateDisplay(shipState, msg)
    return shipState


# INITIALIZATION
conf = cm.loadConfig(confFile)

logging.basicConfig(
    level=conf['loglevel'],
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(conf['logfile'], mode='a'),
        logging.StreamHandler()])
praw_logger = logging.getLogger('praw')
praw_logger.setLevel(logging.CRITICAL)
praw_logger.addHandler(logging.NullHandler())
logging.info("INIT - Logger")

saveFileName = f"./{conf['savedir']}/{conf['savename']}"
databaseName = f"./{conf['savedir']}/{conf['dbname']}"
if not os.path.exists(saveFileName):
    makeSaveFile(saveFileName)
shipState = cm.loadConfig(saveFileName)
dbs.initDBConnection(databaseName)
logging.info("INIT - Game State")

reddit = praw.Reddit(
    client_id     = conf["api_red_clientid"],
    client_secret = conf["api_red_clientsecret"],
    password      = conf["api_red_password"],
    user_agent    = conf["api_red_useragent"],
    username      = conf["api_red_username"])
sub = reddit.subreddit(conf["subReddit"])
logging.info("INIT - Reddit API")

timer = 0  # Initialize process timer
tick  = 0  # Initialize tick counter

# MAIN LOOP - THE BIG ENCHILADA!
while True:
    time_startLoop = perf_counter()
    tick += 1
    shipState = updateShipState(shipState, timer)
    sensorSweep(shipState)
    shipState = crewActions(shipState)
    shipState = isEvent(shipState)
    shipState = finishTick(shipState)
    if tick % 12 == 0:  # Save ShipState to disk every 12 ticks (~1 per minute)
        cm.writeConfig(shipState, saveFileName)
    # Back up the save file roughly every 12 hours
    if tick % 8640 == 0 and not shipState['quikSail']:
        os.system("./backupSave.sh")
        logging.info("Backed up save file.")
    time_stopLoop = perf_counter() - time_startLoop
    if time_stopLoop < 5:
        if shipState['quikSail']:
            sleep(0.5-time_stopLoop)
        else:
            sleep(5-time_stopLoop)
    timer = round(perf_counter() - time_startLoop)

