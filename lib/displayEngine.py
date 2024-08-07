#!/bin/python3

## CHIP'S OCEAN GAME (COG) DISPLAY ENGINE MODULE
##
## Functions to drive the on-console display for COG.


## IMPORTS AND CONSTANTS
import os
import time
from math import floor, ceil

import lib.navigation as nav
import lib.dbServices as dbs
from lib.configManager import loadConfig

CFILE = "./etc/main.conf"
WIDTH = 70
DIV   = '━'*WIDTH


## FUNCTIONS
def updateDisplay(shipState, statusMsg):
    # Updates the status display sent to the console. Takes in the state of the
    # ship as well as a free-hand status message.
    contact = dbs.lookupContact(shipState['trackID'])
    os.system('clear')
    print("")

    # Title bar
    text = f"┥ {conf['hull']} {shipState['name']} ┝"
    print(center(text, '━'))

    # Navigation Pane
    print(header("NAVIGATION"))
    print(f"STATUS: {statusMsg}\n")
    sclock = f"{shipState['day']}-{shipState['tStamp']}"
    ltext = f"TRACK:  {contact}"
    rtext = f"SHIP CLOCK: {lpad(sclock, 8)}"
    print(twoColumn(ltext, rtext))
    shipLoc  = (shipState['shipX'], shipState['shipY'])
    try:
        trackLoc = (contact[0], contact[1])
        distance = round(nav.computeRange(shipLoc, trackLoc), 2)
        eta      = nav.convertETA(nav.computeETA(shipState['spd'], distance))
    except:
        distance = "N/A"
        eta = "N/A"
    ltext = f"DIST:   {distance} nm"
    rtext = f"REAL CLOCK: {lpad(time.strftime('%H:%M:%S', time.localtime()), 8)}"
    print(twoColumn(ltext,rtext))
    print(f"ETA:    {eta}")
    print()
    ltext = f"X: {shipState['shipX']}"
    rtext = f"SPEED: {lpad(round(shipState['spd'], 2), 5)}"
    if 0 < shipState['spd'] <= 3:
        rtext = f"!EMERGENCY SAILS!   SPEED: {lpad(round(shipState['spd'], 2), 5)}"
    print(twoColumn(ltext, rtext))
    ltext = f"Y: {shipState['shipY']}"
    rtext = f"HEADING:   {lpad(round(shipState['hdg']), 3, '0')}"
    print(twoColumn(ltext, rtext))
    print()
    radbase = shipState['range_radar']
    sonbase = shipState['range_sonar']
    radmod  = shipState['mod_radar']
    sonmod  = shipState['mod_sonar']
    radeffective = round(nav.computeEffectiveRange(radbase, radmod))
    soneffective = round(nav.computeEffectiveRange(sonbase, sonmod))
    ltext = f"RADAR RANGE: [{radeffective}] {radbase} ({radmod}%)"
    rtext = f"SONAR RANGE: [{soneffective}] {sonbase} ({sonmod}%)"
    print(twoColumn(ltext, rtext))

    # Ship Health Pane
    print(header("SHIP HEALTH"))
    ltext = f"HULL:       {round(shipState['health_hull'], 2)}"
    rtext = f"ENGINE: {lpad(round(shipState['health_engine'], 2), 5)}"
    print(twoColumn(ltext, rtext))
    ltext = f"LABORATORY: {round(shipState['health_lab'], 2)}"
    rtext = f"BRIDGE: {lpad(round(shipState['health_bridge'], 2), 5)}"
    print(twoColumn(ltext, rtext))
    ltext = f"DINGHY:     {round(shipState['health_dinghy'], 2)}"
    rtext = f"MINISUB: {lpad(round(shipState['health_sub'], 2), 5)}"
    print(twoColumn(ltext, rtext))

    # Engine Stats Pane
    print(header("ENGINE STATUS"))
    fuel = round(shipState['cargo_fuel'], 2)
    cap  = shipState['fuel_cap']
    pct  = round((fuel/cap)*100, 1)
    ltext = f"FUEL: {fuel} ({pct}%)"
    rtext = f"MAX. SPEED: {shipState['max_spd']}"
    print(twoColumn(ltext, rtext))
    print(f"EFF:  {round(shipState['fuel_eff'], 2)} (lpnm)")

    # Crew Stats Pane
    print(header("CREW STATUS"))
    ltext = f" CO: {shipState['co']['name']} ({round(shipState['co']['health'],2)}%)"
    pretext = f"{shipState['cheng']['name']} ({round(shipState['cheng']['health'],2)}%)"
    engtext = f"{shipState['eng']['name']} ({round(shipState['eng']['health'],2)}%)"
    padlen = max(len(pretext), len(engtext))
    rtext = f"CHENG: {lpad(pretext, padlen)}"
    print(twoColumn(ltext, rtext))
    ltext = f"CSO: {shipState['cso']['name']} ({round(shipState['cso']['health'],2)}%)"
    rtext = f"ENG: {lpad(engtext, padlen)}"
    print(twoColumn(ltext, rtext))
    print(columnTruncate(f"SCI: {shipState['sci']['name']} ({round(shipState['sci']['health'],2)}%)"))

    # Cargo Contents Pane
    print(header("CARGO CONTENTS"))
    ltext = f"FOOD: {shipState['cargo_food']}"
    rtext = f"WATER: {lpad(shipState['cargo_water'], 6)}"
    print(twoColumn(ltext, rtext))
    ltext = f"IRON: {shipState['cargo_iron']}"
    rtext = f"SILICON: {lpad(shipState['cargo_silicon'], 6)}"
    print(twoColumn(ltext, rtext))

    # Misc Stats Pane
    print(header("MAIN COMPUTER"))
    ltext = f"UNEXPLORED POIS: {dbs.countTableEntries('TO_EXPLORE')}"
    rtext = f"ARTIFACTS TO BE ANALYZED: {lpad(shipState['to_analyze_artifact'], 2)}"
    print(twoColumn(ltext, rtext))
    ltext = f"  EXPLORED POIS: {dbs.countTableEntries('POI')}"
    rtext = f"TECH TO BE ANALYZED: {lpad(shipState['to_analyze_tech'], 2)}"
    print(twoColumn(ltext, rtext))
    print()
    ltext = f"ODOMETER: {round(shipState['odometer'], 3)}nm"
    rtext = f"DIST-2-HOME: {round(nav.computeRange(shipLoc, (0,0)), 2)}nm"
    print(twoColumn(ltext, rtext))
    print()
    print(f"MONEY: ${round(shipState['money'], 2):,}")
    return

def buildFooter(shipState):
    # Builds a footer message to be attached to the bottom of log messages, 
    # Reddit posts, etc. Conveys most of the same information as the console
    # status display, but in more of a list format.
    div = f"\n{'-'*3}\n\n"
    footer = div
    shipLoc = (shipState['shipX'], shipState['shipY'])
    contact = dbs.lookupContact(shipState['trackID'])
    try:
        trackLoc  = (contact[0], contact[1])
        distance  = round(nav.computeRange(shipLoc, trackLoc), 2)
        eta       = nav.convertETA(nav.computeETA(shipState['spd'], distance))
        trackType = "Surface" if contact[2] == 'U' else "Submerged"
    except:
        trackLoc  = "N/A"
        distance  = "N/A"
        eta       = "N/A"
        trackType = "N/A"

    EffRR = nav.computeEffectiveRange(shipState['range_radar'], shipState['mod_radar'])
    EffSR = nav.computeEffectiveRange(shipState['range_sonar'], shipState['mod_sonar'])

    components = [ 'hull', 'engine', 'lab', 'bridge', 'dinghy', 'sub' ]
    avg = 0
    for component in components:
        avg += shipState[f'health_{component}']
    oHealth = round(avg/len(components))

    fuelpct = (shipState['cargo_fuel']/shipState['fuel_cap'])*100

    footer = f"{footer}{' '*18}SHIP'S STATUS\n\n"

    footer = f"{footer}SHIP'S CLOCK: {shipState['day']}-{shipState['tStamp']}\n\n"

    footer = f"{footer}NAVIGATION:\n\n"
    footer = f"{footer}   LOCATION: {round(shipState['shipX'], 2)}, {round(shipState['shipY'], 2)}\n\n"
    footer = f"{footer}   SPEED:    {shipState['spd']} knots\n\n"
    footer = f"{footer}   HEADING:  {lpad(round(shipState['hdg']),3,'0')}\n\n"

    footer = f"{footer}   TRACK:    {trackLoc} - {trackType}\n\n"
    footer = f"{footer}   DISTANCE: {distance} nautical miles\n\n"
    footer = f"{footer}   ETA:      {eta}\n\n"

    footer = f"{footer}SENSORS:\n\n"
    footer = f"{footer}   EFFECTIVE RADAR RANGE: {round(EffRR)} nm\n\n"
    footer = f"{footer}   EFFECTIVE SONAR RANGE: {round(EffSR)} nm\n\n"

    footer = f"{footer}OVERALL SHIP HEALTH: {oHealth}%\n\n"

    footer = f"{footer}FUEL STATUS: {round(fuelpct, 2)}%\n\n"

    footer = f"{footer}CREW HEALTH:\n\n"
    footer = f"{footer}   Captain:               {shipState['co']['name']} - {shipState['co']['health']}%\n\n"
    footer = f"{footer}   Chief Engineer:        {shipState['cheng']['name']} - {shipState['cheng']['health']}%\n\n"
    footer = f"{footer}   Chief Science Officer: {shipState['cso']['name']} - {shipState['cso']['health']}%\n\n"
    footer = f"{footer}   Engineer:              {shipState['eng']['name']} - {shipState['eng']['health']}%\n\n"
    footer = f"{footer}   Scientist:             {shipState['sci']['name']} - {shipState['sci']['health']}%\n\n"

    footer = f"{footer}CARGO HOLD:\n\n"
    footer = f"{footer}   FOOD:    {shipState['cargo_food']}\n\n"
    footer = f"{footer}   WATER:   {shipState['cargo_water']}\n\n"
    footer = f"{footer}   IRON:    {shipState['cargo_iron']}\n\n"
    footer = f"{footer}   SILICON: {shipState['cargo_silicon']}\n\n"

    return footer

def header(text):
    # Builds a header consisting of two divider bars with the title text
    # sandwiched in between. 
    cText = center(text)
    head = f"{DIV}\n{cText}\n{DIV}"
    return head

def twoColumn(left, right, trunc=True):
    # Takes two strings of text and concatenates them in to a single string,
    # with added whitespace in the middle so that they are arranged as left &
    # right justified columns of proper width.
    if trunc:
        left  = columnTruncate(left)
        right = columnTruncate(right)
    padlen = WIDTH - (len(left)+len(right))
    padding = ' '*padlen
    return f"{left}{padding}{right}"

def columnTruncate(text):
    # If length of string <text> is longer than half of WIDTH, then truncate
    # it to proper length. Used for dividing panel in to columns. Returns
    # truncated (or not) string. 
    colwidth = floor(WIDTH/2)
    rtext = text
    if len(text) > colwidth:
        rtext = text[:colwidth]
    return rtext

def center(text, pad=' '):
    # Centers a string of text in the middle of the screen. Takes in text and
    # pad character as input. Returns the centered string as output.
    leftside  = floor((WIDTH-len(text))/2)
    rightside = ceil((WIDTH-len(text))/2)
    return f"{pad*leftside}{text}{pad*rightside}"

def lpad(text, length, pad=' '):
    # Pads the left side of a string with whitespace to make it a given length.
    # Takes the text and the requested length as input, returns the padded
    # string as output. NOTE: If string is longer than length then it will
    # TRUNCATE the text.
    t = str(text)
    if len(t) > length:
        return t[-length:]
    diff = length - len(t)
    return f"{pad*diff}{t}"


## INITIALIZATION
conf = loadConfig(CFILE)

if __name__ == "__main__":
    dbs.initDBConnection("./testdb.db")


## UNIT TESTS
if __name__ == "__main__":
    shipState = {
                "name"    : "S.S. Guinea Pig",
                "max_spd" : 10,

                "health_hull"   : 100,
                "health_engine" : 75,
                "health_lab"    : 32,
                "health_bridge" : 80,
                "health_dinghy" : 100,
                "health_sub"    : 73,
                "fuel_cap" : 14400,
                "fuel_eff" : 10,
                "shipX"       : 328.5286987,
                "shipY"       : 27.38475847635,
                "hdg"         : 10.8,
                "spd"         : 10,
                "trackID"     : 1,
                "range_radar" : 50,
                "mod_radar"   : 2.3,
                "range_sonar" : 10,
                "mod_sonar"   : -32.2,
                "cargo_food"          : 1000,
                "cargo_water"         : 59835,
                "cargo_iron"          : 1000,
                "cargo_silicon"       : 100,
                "cargo_fuel"          : 8370,
                "to_analyze_tech"     : 20,
                "to_analyze_artifact" : 30,
                "co"    : { "name" : "John Doe", "health" : 26, "fTitle" : "Captain"},
                "cheng" : { "name" : "Jane Doe", "health" : 60, "fTitle" : "Chief Engineer"},
                "cso"   : { "name" : "Bob Smith", "health" : 73, "fTitle" : "Chief Science Officer"},
                "eng"   : { "name" : "Carol Smith", "health" : 96, "fTitle" : "Engineer"},
                "sci"   : { "name" : "Frank Freemont", "health" : 38, "fTitle" : "Scientist"},
                "money"  : 1000,
                "day"    : 36,
                "tStamp" : 83749 }
    msg = "Cruising towards unexplored submerged contact at 123, 456"
    contact = (28, -32, "U")
    dbs.writeContacts([(3, 3, 'L')])

    print("Testing updateDisplay()")
    updateDisplay(shipState, msg)

    # Test buildFooter()
    print("\n\n\n")
    print(buildFooter(shipState))

    # # Test center()
    # print(f"\n\n{DIV}")
    # print(center("Testing center()"))

    # # Test lpad()
    # print(DIV)
    # print(lpad("Testing lpad()", 17))

    # # Test twoColumn()
    # print(DIV)
    # print(twoColumn("Testing twoColumn()", "Hello World!"))
    # print(twoColumn("Also testing columnTruncate() by making a long string.", "Foobar"))

    # # Test header()
    # print()
    # print(header("Testing header()"))