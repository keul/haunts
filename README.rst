=============
B-Open Haunts
=============

.. image:: https://raw.githubusercontent.com/keul/haunts/main/docs/fear-of-the-worklog.jpg
        :target: https://dungeonsdragons.fandom.com/wiki/Haunt
        :alt: Haunt monster

\  

.. image:: https://img.shields.io/pypi/v/haunts.svg
        :target: https://pypi.python.org/pypi/haunts

.. contents:: Table of Contents

What is does
============

Fill Google Calendars with events taken from a Google Spreadsheet.

How to install
==============

.. code-block:: bash

   pip install haunts

Prerequisites
=============

To use Google Calendar and Google Spreasheet APIs you must generate a Google API application and download a *credentials.json*:

* Run ``haunts --config``. It will create the ``~/.haunts`` folder and an ``haunts.ini`` file inside it.
* Edit the ``haunts.ini`` file by setting the ``CONTROLLER_SHEET_DOCUMENT_ID``
* Go to https://console.cloud.google.com/home/dashboard and create a Project called *haunts*.
  
  * In the search bar, search *Credentials APIs and services* and enable it.
  * Click on *Create Credentials*, set *Desktop* as the *type* and save the json file as ``~/.haunts/credentials.json``.
  * In the search bar, search *Google Sheets API* and *Google Calendar API* and activate them.
  
* Run ``haunts`` normally.
  It will ask you to authenticate to both the Google Sheets and the Google Calendar APIs (a browser should be automatically opened for you).
  This action will create the following files: ``~/.haunts/calendars-token.json`` and ``~/.haunts/sheets-token.json``

How to use
==========

Command line help is accessible using:

.. code-block:: bash

   haunts --help

Usage

.. code-block:: bash

   haunts <SHEET_NAME>

You can limits events interaction to a single day, or a set of days by using the ``-d`` parameter (can be used multiple times):

.. code-block:: bash

   haunts --day=2021-07-08 <SHEET_NAME>

How it works
------------

The command will try to access a Google Spreatsheet you must own (write access required), specifically it will read a single sheet at time inside the spreadsheet.

Sheet definition
----------------

The referenced sheet must contains a set of columns. Headers names are important but orders matters not.
Any additional columns will be ignored.

An `example sheet
<https://docs.google.com/spreadsheets/d/18ADhaNhEyr05cyNqXU-o-V4ialrzW9CS3XiFLM-glT4/edit#gid=998726384>`_ is provided.

The partition in multiple sheets is designed to keep every month in a separate sheet, but this is not strictly checked.

Every sheet should contains following headers:

**Date**
  (date)
  
  The day where the event will be created

**Start time**
  (time string in format ``HH:MM`` or empty) - *optional column*
  
  If provided, the current event will start at given time. This will influence also events defined after this row

**Spent**
  (number or empty)
  
  How long the event will last. Leave empty to create a full-day event

**Project**
  (string)
  
  Project name as it's named in the *config* sheet (see below)

**Activity**
  (string)
  
  Summary of the event

**Details**
  (string, optional)
  
  Additional text for the event description

**Event id**
  (string)
  
  Leave this empty. It will be filled with the id of the generated event

**Link**
  (text)
  
  Leave this empty. It will be filled with a link to the event inside Google Calendar

**Action**
  (char)
  
  See below. If empty: it will be filled with an ``I`` when an event is created

Configuring projects
~~~~~~~~~~~~~~~~~~~~

The spreadsheet must also contains a *configuration sheet* (default name is ``config``, can be changed in the .ini) where you must put two columns (with headers):

**id**
  The id of a Google Calendar associated to this project.
  You must have write access to this calendar.

**name**
  The name of the project, like an alias to the calendar

A project name can be associated to the same calendar id multiple times.

Values in the ``name`` column are the only valid values for the ``Project`` column introduced above

How events will be filled
-------------------------

Let says you run something like this:

.. code-block:: bash

   haunts --day=2021-07-08 July

*haunts*  will access the sheet named ``July`` in the spreadsheet configured in the .ini file.
Only rows where the ``Date`` filed will match the ``--day`` parameter will be considered (if this param is not provided: the full sheet content is analyzed).

For every rows that match, *haunts* will:

- Generate a new event, starting from a default time (this can be configured in the .ini).
  The event will last for ``Spent`` hours
- The next event will start where the previous ended
- If the event will be successfully created, an "I" will be placed in the ``Action`` column.
  This will make future executions to ignore the line.
- Other columns will be read or filled as described above.

Actions
-------

Possible values you can find (or put yourself) in the ``Action`` column:

- ``I``
  
  *Ignore*: execution will just ignore this line
- ``D``
  
  *Delete*: execution will clear ``Action``, ``Event id`` and ``Link`` cells for this row, and delete the related calendar event.
  So: next execution will likely fill this line again (this is a poor-man-edit)

TODO and known issues
=====================

* Rows in the sheet must be sorted ascending
* *haunts* will not check for already filled time slots (yet?), so overlapping of events may happens

Why?!
=====

In `B-Open
<https://www.bopen.eu/>`_ this is how we register our worklogs, participation to projects in multiple Google Calendars.

OK, but why "haunts"?!
----------------------

An haunt is a monster from `Dungeons&Dragons
<https://dungeonsdragons.fandom.com/wiki/Haunt>`_, which is translated in the italian version of the game as "Presenza".

But "presenza" is the same term used in italian for "participation", so how we call our worklogs.

And filling worklogs haunt us.

.. image:: https://raw.githubusercontent.com/keul/haunts/main/docs/pm.gif

Credits
=======

Developers and contributors.

* keul <l.fabbri@bopen.eu> (main worklogs hater)
* francesconazzaro (how-to-use-google-api-evangelist)
