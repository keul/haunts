============
B-Open Haunt
============

.. image:: https://img.shields.io/pypi/v/haunts.svg
        :target: https://pypi.python.org/pypi/haunts

.. image:: ./docs/haunt.gif
        :target: https://dungeonsdragons.fandom.com/wiki/Haunt
        :alt: Haunt monster

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

To use Google Calendar and Google Spreasheet APIs you must generate a Google API application and download a *credentials.json*.
This file must be put inside the ``~/.haunts`` directory (this will be generated automatically, see below).

See https://cloud.google.com/docs/authentication/getting-started

How to use
==========

Command line help is accessible using:

.. code-block:: bash

   haunts --help

Usage

.. code-block:: bash

   haunts <SHEET_NAME>

The first time ``haunts`` will be run, it just create an `.haunts` folder in your home directory with configuration files inside, then it exits.
You *must* edit the ``~/.haunts/haunts.ini`` file.

Following run attempts will work normally.

You can also limits events interaction to a single day, or a set of days by using the ``-d`` parameter (can be used multiple times):

.. code-block:: bash

   haunts --day=2021-07-08 <SHEET_NAME>

How it works
------------

The command will try to access a Google Spreatsheet you must own (write access required), specifically it will read a single sheet inside the spreadsheet.

Month sheet definition
----------------------

The referenced sheet must contains a set of columns (with headers defined below) but orders matters not.
Also: additional columns can be added and they will be ignored.

The partition in multiple sheets is designed to keep every month in a separate sheet, but this is not strictly checked.

Sheet format should be:

**Date**
  (date)
  
  The day where the event will be created

**Spent**
  (number or empty)
  
  How long the event will last. Leave empty to create a full-day event.

**Project**
  (number)
  
  Project name (see below)

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
  
  Leave this empty. It will be filled with a link to the event inside Google Calendar.
  Put an ``I`` manually if you want to ignore an entry and avoid event creation.

**Action**
  (char)
  
  See below. If emtpy: it will be filled with an ``I`` when an event is created

Configuring projects
--------------------

The spreadsheet must also contains a *configuration sheet* (default name is ``config``, can be changed in the .ini) where you must put two columns (with headers):

**id**
  The id of the Google Calendar associated to this project.
  You must have write access to this calendar.

**name**
  The name of the project, like an alias to the calendar

A project name can be associated to the same calendar id multiple times.

Values in the ``name`` columns are the only valid values for the ``Project`` column introduced above

How events will be filled
-------------------------

Let says you run something like this:

.. code-block:: bash

   haunts --day=2021-07-08 July

*haunts*  will access the sheet named ``July`` in the spreadsheet configured in the .ini file.
Only rows where the ``Date`` filed will match the ``--day`` parameter will be considered.

For every rows that match, *haunts* will:

- Generate a new event, starting from a default time (this can be configured in the .ini).
  The event will last for ``Spent`` hours
- The next event will start where the previous ended
- If the event will be successfully created, an *I* will be placed in the ``Action`` column.
  This will make other execution of *haunts* to ignore the line.
- Other columns will be read or filled as described above.

TODO and known issues
=====================

* **Rows in the sheet must be sorted ascending**
* Other actions maybe? Like *E* (for edit)
* *haunts* will not check for already filled time slots (yet?), so overlapping of events may happens

Why?!
=====

In `B-Open
<https://www.bopen.eu/>`_ this is how we register our worklogs, participation to projects in multiple Google Calendars.

OK, but why "haunts"?!
----------------------

An haunt is a monster from `Dungeond&Dragons
<https://dungeonsdragons.fandom.com/wiki/Haunt>`_, which was translated to italian as "Presenza".

But "presenza" is the same term used in italian for "participation", so how we call our worklogs.

And filling worklogs haunt us.

Credits
=======

Developer and contributors.

* keul <l.fabbri@bopen.eu> (main worklogs hater)
