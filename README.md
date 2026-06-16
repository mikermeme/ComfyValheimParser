parseRewind turns rewind files into json

Download all the files and put them in the same directory.
parseRewind expects rewind.hexpat in there to un-hashcode the ZDOvar names

```
python parseRewind.py Your_Rewind_file
```


python parseItems.py takes .db world saves or the .json output from either valheim-save-tools or parseRewind. It will call valheim-save-tools and make a temporary json if you point it at a world file

```
python parseItems.py Your_World_Save.db
```
or
```
python parseItems.py Your_Parsed_World_Save.json
```
or
```
python parseItems.py Your_Parsed_Rewind.json
```