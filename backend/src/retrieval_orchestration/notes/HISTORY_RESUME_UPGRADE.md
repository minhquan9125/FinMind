# Chọn và mở lại phiên JSON

Only3editablefiles: retrieval_flow/history.py, hoi.py, tests/test_history_resume.py.
Do not change conversation.py/core modules/oldtests/history files. Stdlib, fixture-only.
Prior dependent job improves conversation but retains public API. Runtime actual
approved conversation candidate and unchanged4upstream modules staged for tests.

ChatSession(session_id=None,today=None), async ask(str)->envelope, reset(), today=date
settable, last_decision/last_result deepcopy, context_summary()->str, session_id UUID.
hoi.py save_history(history,directory=None)->Path stays compatible UTF8 indent2
exclusivefile, timestamps/fullUUID; default adjacent chat_history. Existing main
persistFalse/history_dirNone ->dict, __main__ persistTrue, logs ordered user and
assistant with content,timestamp and result forfinancial replies. /moi logs reset.

Implement in history.py:
- load_history(filename:str,directory:Path)->dict. Only basename .json inside directory,
  no absolute/traversal/symlink/junction; max2MiB via boundedread (not truststat only).
  Validate whole history before any activation: schema_version1.0, session_id nonblank
  <=128chars, started_at/saved_at timezoneawareISO timestamps, messages list <=2000,
  role user/assistant, contentstring<=40000chars, timezoneaware timestamp. Optional
  reference_date must ISOdate; root +user messages. Unknownextra/result fields ignored
  for replay, never execute/import/apply savedassistantnumbers or decision/scope.
  Bad JSON/encoding/types/versions/deep nesting =>ValueError useful Vietnamese; OS
  errors handled by CLI. Paths supplied by user never outside directory even readonly.
- list_histories(directory:Path)->list[dict] valid file descriptors name,saved_at,
  session_id,turns,preview (first user content <=80 chars with control chars stripped).
  Newest saved_at first with stable name tie-break; invalid files skipped, absentdir
  empty. Do not modify files. All displayed indices refer to this orderedlist.
- async restore_session(history:dict, today:date|None=None)->ChatSession validates
  fullhistory then creates NEW session UUID. Replay ONLY savedusertext via ask;
  /moi resets; /json and other saved UIcommands do not invoke retrieval. Ignore all
  assistant result fields as untrusted. Bound messagecount above. Historical relative
  dates use user.reference_date ifpresent else that user's timestamp at UTC+07 (legacy
  histories supported); reset session.today to trusted current UTC+07/today after
  replay so NEW nămnay uses currentyear. No cross-session evidenceIDs imported.
  Failed replay raises and must not change active CLI session or sourcefile.

CLI commands without startup blockers:
`/lichsu`: list descriptors numbered, emptyfriendly. `/mo 1` or `/mo basename.json`
opens validated session, print resumed scope summary; `/tomtat` context_summary;
`/help` commandhelp. Bad selectors/files report readable and keep active scope.
`/moi`, `/json`, exit/EOF/CtrlC unchanged. Blank no-op. No arbitrary fullpaths.
When successful /mo: childdoc messages=deepcopy old messages, keep originalstarted_at,
new session_id and metadata resumed_from basename,parent_session_id oldid,continued_at.
New file when saved never overwrite original. Continue logging newturns tochilddoc.
Each newuser message logs reference_date=session.today.isoformat() forfuture replay.
Do NOT log /lichsu,/mo,/help,/tomtat as user financialutterances. /moi stays transcript.
Bad/missing source does not clear currentmessages. No saving unchanged openedhistory
when exit with no new turns (avoid phantom duplicates). Preserve main default no
disk and existing tests expecting count/reset/cancellation/OSError behavior.

No user realhistory content sent to workers. Generated testfixtures only, tempfiles
within candidate .agent-state. Testlegacy/newjson, resume→sau thuế, freshrelativeyear,
/moi, tamperedassistant ignored, malformed/oversize/traversal/symlink failclosed,
badload leavesactive query, childfile originalbytes unchanged, newcommands no retrieval.
No network/subprocess/fileoutside taskfolder, no packageinstall/gitcommit.
