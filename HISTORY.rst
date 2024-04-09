History
=======

0.7.0 (2024-04-09)
------------------

- Added ``read`` option to ``--execute``


0.6.0 (2023-03-31)
------------------

- Added ``II`` action

0.5.0 (2022-12-04)
------------------

- Renamed ``--action`` to ``--execute``
- new option:``--action`` to filter by values on "Action" column
- new option:``--overtime`` to just report overtime amount

0.4.0 (2022-12-01)
------------------

- Added ``-p`` parameter, to just act on specific project(s)
- Added ``--action``, and implemented ``report`` action (credits to @gcammarota)
- More detailed logging when deleting events with action ``D``

0.3.1 (2022-11-21)
------------------

- bugfix: if a row uses an ``I`` action, everything there is ignored
- When a project is not found: do not stop haunts but skip the line and report that when execution ends.
  Closes #14
- Empty lines now supported.
  Closes #12
- Human readable error message when the sheet is not found.
  Closes #11

0.3.0 (2022-05-02)
------------------

- Fixed: ``START_TIME`` default was not used.
  Closes #4
- New: new action: ``D``
- New: added "Start time" feature.
  Closes #7
- Fix: reduces number of writes.
  Closes #6
- Fix: do not fail badly when max number of requests per minutes is reached.
  See #1
- New: added "--config" for initial env configuration, improved documentation

0.2.1 (2022-02-10)
------------------

- Fixed full day criteria

0.2.0 (2021-07-29)
------------------

- Added support for full-day event

0.1.0 (2021-07-10)
------------------

* Initial release
