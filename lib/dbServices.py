#!/bin/python3

## CHIP'S OCEAN GAME (COG) DATABASE MODULE
##
## Functions related to interfacing with the game's database.


# IMPORTS AND CONSTANTS
import sqlite3
import json
import os

from lib.configManager import loadConfig

conffile = "./etc/main.conf"


# FUNCTIONS
def makeDB(filename):
    # Creates and initializes the sqlite3 database. Takes in the filename of
    # the new database as input. Does not return any output.
    if os.path.exists(filename):
        print("Database already exists - no need to create it")
        return

    db = sqlite3.connect(filename)
    cursor = db.cursor()

    tab_poi = """ CREATE TABLE POI (
                  pid INTEGER PRIMARY KEY,
                  locX INTEGER,
                  locY INTEGER,
                  type TEXT,
                  name TEXT,
                  adj TEXT,
                  weird INTEGER,
                  desc TEXT,
                  images TEXT,
                  items TEXT); """
    tab_toexplore = """ CREATE TABLE TO_EXPLORE (
                        eid INTEGER PRIMARY KEY,
                        locX INTEGER,
                        locY INTEGER,
                        type TEXT); """
    homeport = """ INSERT INTO POI (locX, locY, type, name, weird)
                   VALUES (0, 0, 'homeport', 'Port Endeavour', 1) """
    boldlygo = """ INSERT INTO TO_EXPLORE (locX, locY, type)
                   VALUES (0, 0, 'B') """
    
    cursor.execute(tab_poi)
    cursor.execute(tab_toexplore)
    cursor.execute(homeport)
    cursor.execute(boldlygo)
    cursor.close()
    db.commit()
    db.close()
    return

def lookupContact(eid):
    # Looks up a contact from the to_explore table by its EID number. Takes in
    # the database object and requested EID as input, returns the contact as a
    # tuple.
    cursor = db.cursor()
    command = "SELECT locX, locY, type FROM TO_EXPLORE WHERE eid == ?"
    cursor.execute(command, (eid,))
    result = cursor.fetchone()
    cursor.close()
    try:
        contact = (result[0],result[1],result[2])
    except:
        contact = None
    return contact

def lookupEID(loc):
    # Looks up the EID for a contact located at <loc> (tuple) from the
    # to_explore table. Takes db object and location, returns EID as int.
    # Returns None if the requested coords don't exist in the database.
    cursor = db.cursor()
    command = "SELECT eid FROM TO_EXPLORE WHERE locX == ? AND locY == ?;"
    cursor.execute(command, (loc[0], loc[1],))
    result = cursor.fetchall()
    cursor.close()
    if len(result) > 0:
        return result[0][0]
    else:
        return None

def lookupPID(loc):
    # Looks up the EID for a contact located at <loc> (tuple) from the
    # to_explore table. Takes db object and location, returns EID as int.
    cursor = db.cursor()
    command = "SELECT pid FROM POI WHERE locX == ? AND locY == ?;"
    cursor.execute(command, (loc[0], loc[1],))
    try:
        result = int(cursor.fetchone()[0])
    except:
        result = None
    cursor.close()
    return result

def deleteEID(eid):
    # Deletes a record from the to_explore table, identified by EID.
    cursor = db.cursor()
    command = "DELETE FROM TO_EXPLORE WHERE eid == ?;"
    cursor.execute(command, (eid,))
    db.commit()
    cursor.close()
    return

def countTableEntries(table):
    # Count how many entries are in a table. Returns an int.
    cursor = db.cursor()
    command = f"SELECT * FROM {table};"
    cursor.execute(command)
    result = cursor.fetchall()
    return len(result)-1

def loadPOI(pid):
    # Loads already-discovered POI data from the database. Takes in the DB
    # connection and requested PID as input, returns list containing the 
    # associated POI record.
    cursor = db.cursor()
    command = """ SELECT type, name, adj, weird, desc, images 
                  FROM POI WHERE pid == ?; """
    cursor.execute(command, (pid,))
    result = cursor.fetchone()
    cursor.close()
    return result

def writePOI(contact, pProps, desc, images):
    # Creates a new record in the POI table. Takes in location and pProp data
    # as well as a list of captured images, returns nothing as output. 
    cursor = db.cursor()

    locX  = contact[0]
    locY  = contact[1]
    type  = pProps['type']
    name  = pProps['name']
    adj   = pProps['adj']
    weird = pProps['weirdness']
    imags = json.dumps(images)

    command = """ INSERT INTO POI (locX, locY, type, name, adj, weird, desc, images) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?); """
    
    cursor.execute(command, (locX, locY, type, name, adj, weird, desc, imags,))
    db.commit()
    cursor.close()
    return

def writeContacts(contacts):
    # Writes a list of contacts to the TO_EXPLORE table. Contacts are taken as
    # a list of tuples (X coord, Y coord, Surface/Submerge). Returns no output.
    cursor = db.cursor()
    command = """ INSERT INTO TO_EXPLORE (locX, locY, type)
                  VALUES (?, ?, ?); """
    
    for contact in contacts:
        cursor.execute(command, contact)
    
    db.commit()
    cursor.close()
    return

def updatePOI(pid, images):
    # Updates an existing POI record with new images. Takes the list of image
    # files as input as well as the pid of the relevant record. Returns no
    # output.
    cursor = db.cursor()
    imags = json.dumps(images)
    command = """ UPDATE POI SET images = ? WHERE pid == ?; """
    cursor.execute(command, (imags, pid,))
    db.commit()
    cursor.close()
    return

def updateBold(loc):
    # Updates the "Boldly Go" record, a.k.a. EID #1. Used when the captain
    # wants to set a track that isn't actually tied to a real contact.
    cursor = db.cursor()
    command = """ UPDATE TO_EXPLORE SET locX = ?, locY = ? WHERE eid == 1; """ 
    cursor.execute(command, (loc[0], loc[1],))
    db.commit()
    cursor.close()
    return 

def initDBConnection(filename):
    # Kicks off a connection to the database so that it's available for other
    # function calls. If the DB file doesn't exist yet, it will call makeDB()
    # to create it. Technically doesn't return output but leaves the open db
    # object as global so that it's ready and available.
    global db
    if not os.path.exists(filename):
        makeDB(filename)
    db = sqlite3.connect(filename)
    return

def dumpAllContacts():
    # Provides the entire exploration queue. Returns the contacts along with
    # their associated EIDs as a list of tuples in the form of 
    # (eid, (X,Y,surf/sub)).
    cursor = db.cursor()
    command = "SELECT * FROM TO_EXPLORE WHERE eid != ?;"
    cursor.execute(command, "1")
    results = cursor.fetchall()
    cursor.close()
    contacts = []
    for result in results:
        contacts.append((result[0], (result[1], result[2], result[3])))
    return contacts

def dumpSurfaceContacts():
    # Returns the locations of all known-but-unexplored surface contacts.
    # Returns the contacts along with their associated EIDs as list of lists:
    # (eid, (X,Y,type))
    cursor = db.cursor()
    command = "SELECT eid, locX, locY FROM TO_EXPLORE WHERE type = ?;"
    cursor.execute(command, ("U",))
    results = cursor.fetchall()
    cursor.close()
    contacts = []
    for result in results:
        contacts.append((result[0], (result[1], result[2], "U")))
    return contacts

def dumpType(type):
    # Returns the locations of all explored POIs of <type>. Returns the
    # contacts along with their associated pids as a list of tuples in the form
    # of (pid, (X,Y,surf/sub)).
    contacts = []
    cursor = db.cursor()
    command = "SELECT pid, locX, locY, type FROM POI WHERE type = ?;"
    cursor.execute(command, (type,))
    results = cursor.fetchall()
    cursor.close()
    for result in results:
        cType = "U" if result[3] in types['surface_pois'] else "L"
        contacts.append((result[0], (result[1], result[2], cType)))
    return contacts


# INITIALIZATION
conf = loadConfig(conffile)
types = loadConfig(f"./{conf['typefile']}")


# UNIT TESTS
if __name__ == "__main__":
    import random
    testfile = "./testdb.db"

    # Test 1: Making a database.
    makeDB(testfile)
    print(f"TEST 1: makeDB() - Created new database at {testfile}.\n")

    # Test 2: Initializing the database.
    initDBConnection(testfile)
    print(f"TEST 2: initDBConnection() - connected to db object {db}\n")

    # Test 3: Writing contacts in to TO_EXPLORE
    contacts = [ (  0,  0, "U"),
                 ( 10, 10, "L"),
                 ( 19, 88, "U"),
                 ( 10,  5, "L"),
                 (181, 27, "L") ]
    writeContacts(contacts)
    print(f"TEST 3: writeContacts() - Wrote {len(contacts)} contacts to TO_EXPLORE\n")

    # Test 4: Counting how many records in TO_EXPLORE
    numContacts = countTableEntries("TO_EXPLORE")
    print(f"TEST 4: countTableEntries() - Found {numContacts} contacts in the database out of {len(contacts)} expected\n")

    # Test 5: Finding the exploration identifier (EID) of a contact at a given
    #         location
    loc = (19, 88)
    eid = lookupEID(loc)
    print(f"TEST 5: lookupEID() - {loc} has an exploration identifier of {eid}, expected 4\n")

    # Test 6: Loading a contact from a given EID
    eid = 5
    contact = lookupContact(eid)
    print(f"Test 6: lookupContact() - Contact #{eid} is {contact}, expected (10, 5, 'L')\n")

    # Test 7: Deleting a contact from TO_EXPLORE
    eid = 2
    deleteEID(eid)
    print(f"Test 7: deleteEID() - Deleted contact #{eid}")
    print(f"        EID is now reporting as {lookupContact(eid)}, expected None")
    print(f"        There are now {countTableEntries('TO_EXPLORE')} contacts in the database, expected 4\n")

    # Test 8: Adding POIs to the POI table
    contact = (random.randrange(100),random.randrange(100),"U")
    pProps = {'type':'island', 'name':'Luna Island', 'adj':'peaceful', 
              'weirdness':random.randrange(10)}
    desc = "The quick brown fox jumps over the lazy dog."
    images = ['123.png', '456.png', '789.png']
    writePOI(contact, pProps, desc, images)
    contact = (random.randrange(100),random.randrange(100),"L")
    pProps = {'type':'wreck', 'name':'Echo Wreck', 'adj':'lovecraftian', 
              'weirdness':random.randrange(10)}
    desc = "abcdefghijklmnopqrstuvwxyz"
    images = ['1011.png', '1213.png', '1415.png']
    writePOI(contact, pProps, desc, images)
    contact = (103,-28,"U")
    pProps = {'type':'offshore platform', 'name':'Armstrong Offshore Platform', 
              'adj':'hazardous', 'weirdness':random.randrange(10)}
    desc = "Testing databases woooo!"
    images = ['apple.png', 'banana.png', 'carrot.png']
    writePOI(contact, pProps, desc, images)
    contact = (321,185,"U")
    pProps = {'type':'offshore platform', 'name':'Aldrin Offshore Platform', 
              'adj':'hazardous', 'weirdness':random.randrange(10)}
    desc = "Rock will never die!"
    images = ['abby.png', 'zoe.png', 'sophie.png']
    writePOI(contact, pProps, desc, images)
    contact = (11,12,"L")
    pProps = {'type':'deposit', 'name':'Samurai Deposit', 
              'adj':'hazardous', 'weirdness':random.randrange(10)}
    desc = "Don't Fade Away"
    images = ['Johnny.png', 'Kerry.png', 'Nancy.png']
    writePOI(contact, pProps, desc, images)
    print(f"Test 8: writePOI() - Added five locations to POI\n")

    # Test 9: Loading POI data from the table
    pid = 2
    poiData = loadPOI(pid)
    images = json.loads(poiData[5])
    print(f"Test 9: loadPOI() - Loading data for PID#{pid}")
    print(f"        Type:        {poiData[0]}")
    print(f"        Name:        {poiData[1]}")
    print(f"        Adjective:   {poiData[2]}")
    print(f"        Weirdness:   {poiData[3]}")
    print(f"        Description: {poiData[4]}")
    print(f"        Images:      {images}\n")

    # Test 10: Looking up a PID from grid coordinates
    loc = (103, -28)
    pid = lookupPID(loc)
    print(f"Test 10: lookupPID() - {loc} has a POI Identifier of {pid}, expected 4\n")

    # Test 11: Updating a POI record that already exists
    images = ['1011.png', '1213.png', '1415.png', 'success.png']
    pid = 3
    updatePOI(pid, images)
    poiData = loadPOI(pid)
    limages = json.loads(poiData[5])
    print(f"Test 11: updatePOI() - Added {limages[3]} to POI#{pid}, expected 'success.png'\n")

    # Test 12: Dumping all surface contacts
    print(f"Test 13: dumpSurfaceContacts() - Detected-but-unexplored contacts:")
    contacts = dumpSurfaceContacts()
    for contact in contacts:
        print(f"         {contact}")
    print()
    
    # Test 13: Dumping types
    print(f"Test 13: dumpType() - Dumping POIs of a given type:")
    print(f"    Offshore Platforms:")
    platforms = dumpType("offshore platform")
    for platform in platforms:
        print(f"        {platform}")
    print(f"    Fuel sources (platforms & deposits):")
    fSrc = dumpType("offshore platform")
    fSrc = fSrc + dumpType("deposit")
    for src in fSrc:
        print(f"        {src}")
    print(f"    Deposits:")
    deposits = dumpType("deposit")
    for depo in deposits:
        print(f"        {depo}")
    print()

    # Test 14: Dumping explore queue
    print(f"Test 14: dumpAllContacts() - All the contacts in TO_EXPLORE:")
    contacts = dumpAllContacts()
    for contact in contacts:
        print(f"    {contact}")
    print()

    # Test 15: Setting a "Boldly Go" track
    print(f"Test 15: updateBold() - Set a 'Boldly Go' track")
    updateBold((3,8))
    contact = lookupContact(1)
    print(f"EID #1 is now {contact}, expect (3, 8, 'B')\n")

