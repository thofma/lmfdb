import json
import lmfdb.inventory_app.inventory_helpers as ih
import lmfdb.inventory_app.lmfdb_inventory as inv
import lmfdb.inventory_app.inventory_db_core as invc
from lmfdb.inventory_app.inventory_upload_data import (upload_collection_structure, extract_specials, delete_all_tables, recreate_rollback_table, MAX_SZ, delete_by_collection)

def upload_all_structure(db, structure_dat):
    """Upload an everything from a structure json document

        db -- LMFDB connection to inventory database
        structure_dat -- JSON document containing all db/collections to upload
    """

    inv.log_dest.info("_____________________________________________________________________________________________")
    inv.log_dest.info("Processing structure data")
    n_dbs = len(structure_dat.keys())
    progress_tracker = 0

    for DB_name in structure_dat:
        progress_tracker += 1
        inv.log_dest.info("Uploading " + DB_name+" ("+str(progress_tracker)+" of "+str(n_dbs)+')')
        invc.set_db(db, DB_name, DB_name)

        for coll_name in structure_dat[DB_name]:
            inv.log_dest.info("    Uploading collection "+coll_name)
            orphaned_keys = upload_collection_structure(db, DB_name, coll_name, structure_dat, fresh=False)
            if len(orphaned_keys) != 0:
                with open('Orph_'+DB_name+'_'+coll_name+'.json', 'w') as file:
                    file.write(json.dumps(orphaned_keys))
                    inv.log_dest.info("          Orphans written to Orph_"+ DB_name+'_'+coll_name+'.json')

def upload_from_files(db, master_file_name, list_file_name, fresh=False):
    """Upload an entire inventory. CLOBBERS CONTENT

        db -- LMFDB connection to inventory database
        master_file_name -- path to report tool database structure file
        list_file_name -- path to file containing list of all additional inventory info files
        fresh -- set to sync tables according to whether this is a fresh or new upload
    """
    #For a complete upload is more logical to fill things in thing by thing
    #so we do all the db's first, then the collections and finish with the additional description

    decoder = json.JSONDecoder()
    structure_dat = decoder.decode(read_file(master_file_name))

    inv.log_dest.info("_____________________________________________________________________________________________")
    inv.log_dest.info("Processing autogenerated inventory")
    n_dbs = len(structure_dat.keys())
    progress_tracker = 0

    for DB_name in structure_dat:
        progress_tracker += 1
        inv.log_dest.info("Uploading " + DB_name+" ("+str(progress_tracker)+" of "+str(n_dbs)+')')
        invc.set_db(db, DB_name, DB_name)

        for coll_name in structure_dat[DB_name]:
            inv.log_dest.info("    Uploading collection "+coll_name)
            orphaned_keys = upload_collection_structure(db, DB_name, coll_name, structure_dat, fresh=fresh)
            if len(orphaned_keys) != 0:
                with open('Orph_'+DB_name+'_'+coll_name+'.json', 'w') as file:
                    file.write(json.dumps(orphaned_keys))
                inv.log_dest.info("          Orphans written to Orph_"+ DB_name+'_'+coll_name+'.json')

    inv.log_dest.info("_____________________________________________________________________________________________")
    inv.log_dest.info("Processing additional inventory")
    file_list = read_list(list_file_name)
    last_db = ''
    progress_tracker = 0
    for file in file_list:
        data = decoder.decode(read_file(file))
        record_name = ih.get_description_key(file)
        DB_name = record_name[0]
        if DB_name != last_db:
            inv.log_dest.info("Uploading " + DB_name+" ("+str(progress_tracker)+" of <="+str(n_dbs)+')')
            last_db = DB_name
            progress_tracker += 1
        coll_name = record_name[1]
        inv.log_dest.info("    Uploading collection "+coll_name)

        upload_collection_description(db, DB_name, coll_name, data)


def upload_collection_from_files(db, db_name, coll_name, master_file_name, json_file_name, fresh=False):
    """Freshly upload inventory for a single collection. CLOBBERS CONTENT

        db -- LMFDB connection to inventory database
        db_name -- Name of database this collection is in
        coll_name -- Name of collection to upload
        master_file_name -- path to report tool database structure file
        json_file_name -- path to file containing additional inventory data
        fresh -- set to skip some syncing if this is a fresh or new upload
    """

    decoder = json.JSONDecoder()

    inv.log_dest.info("Uploading collection structure for "+coll_name)
    structure_data = decoder.decode(read_file(master_file_name))

    #Do we need to keep the orphans?
    #orphaned_keys = upload_collection_structure(db, db_name, coll_name, structure_data, fresh=fresh)
    upload_collection_structure(db, db_name, coll_name, structure_data, fresh=fresh)

    inv.log_dest.info("Uploading collection description for "+coll_name)
    data = decoder.decode(read_file(json_file_name))
    upload_collection_description(db, db_name, coll_name, data, fresh=fresh)

def upload_collection_description(db, db_name, coll_name, data, fresh=False):
    """Upload the additional description

    db -- LMFDB connection to inventory database
    db_name -- Name of database this collection is in
    coll_name -- Name of collection to upload
    data -- additional data as json object for this collection
    fresh -- whether to delete existing info (otherwise extra description will be added, overwriting if required, but anything absent from new info will not be clobbered

    Note this only uploads actual data. All mandatory fields should have been filled by the structure upload
    """

    try:
        db_entry = invc.get_db_id(db, db_name)
        _c_id = invc.get_coll_id(db, db_entry['id'], coll_name)
        if not (db_entry['exist'] and _c_id['exist']):
            #All dbs/collections should have been added from the struc: if not is error
            inv.log_dest.error("Cannot add descriptions, db or collection not found")
            return
    except Exception as e:
        inv.log_dest.error("Failed to refresh collection "+str(e))

    try:
        split_data = extract_specials(data)
        #Insert the notes and info fields into the collection
        try:
            notes_data = split_data[inv.STR_NOTES]
            notes_data = ih.blank_all_empty_fields(notes_data)
            inv.log_dest.debug(notes_data)
        except Exception:
            notes_data = None
        try:
            info_data = split_data[inv.STR_INFO]
            info_data = ih.blank_all_empty_fields(info_data)
            inv.log_dest.debug(info_data)
        except Exception:
            info_data = None
        _c_id = invc.set_coll(db, db_entry['id'], coll_name, coll_name, notes_data, info_data)
    except Exception as e:
        inv.log_dest.error("Failed to refresh collection info "+str(e))

    try:
        for field in split_data['data']:
            dat = split_data['data'][field]
            if not ih.is_record_name(dat):
                inv.log_dest.info("            Processing "+field)
                invc.set_field(db, _c_id['id'], field, dat, type='human')
            else:
                inv.log_dest.info("            Processing record "+field)
                #Data may not actually contain the name or description fields
                rec_set = {'hash':field}
                try:
                    rec_set['name'] = dat['name']
                except Exception:
                    pass
                try:
                    rec_set['description'] = dat['description']
                except Exception:
                    pass
                invc.set_record(db, _c_id['id'], rec_set, type='human')

    except Exception as e:
        inv.log_dest.error("Failed to refresh collection "+str(e))

def read_file(filename):
    """Read entire file contents """
    with open(filename, 'r') as in_file:
        dat = in_file.read()
    return dat

def read_list(listfile):
    """Read file line-wise into list of lines """
    with open(listfile, 'r') as in_file:
        lines = in_file.read().splitlines()
    return lines

#Initial uploader routines ---------------------------------------------------------------

def fresh_upload(master_file_name, list_file_name):
    """Delete existing data and upload a fresh copy.
    CLOBBERS ALL EXISTING CONTENT

    Arguments:

    - master_file_name -- path to structure file from report tool (e.g. lmfdb_structure.json)

    - list_file_name -- path to file containing names of all json files to upload (one per collection)
    """
    got_client = inv.setup_internal_client(editor=True)
    if not got_client:
        inv.log_dest.error("Cannot connect to db")
        return
    db = inv.int_client[inv.get_inv_db_name()]

    #DELETE all existing inventory!!!
    delete_all_tables(db)

    upload_from_files(db, master_file_name, list_file_name, fresh=True)
    recreate_rollback_table(db, MAX_SZ)

def fresh_upload_coll(db_name, coll_name, master_file_name, json_file_name):
    """Delete existing data and upload a fresh copy for a single collection.
    CLOBBERS ALL EXISTING CONTENT FOR THIS COLLECTION

    Arguments:

    - db_name -- name of database to refresh
    - coll_name -- name of collection to refresh
    - master_file_name -- path to structure file from report tool (entire or single collection)
    - json_file_name -- path to additional json file for this collection
    """
    got_client = inv.setup_internal_client(editor=True)
    if not got_client:
        inv.log_dest.error("Cannot connect to db")
        return
    db = inv.int_client[inv.get_inv_db_name()]

    delete_by_collection(db, db_name, coll_name)
    upload_collection_from_files(db, db_name, coll_name, master_file_name, json_file_name, fresh=True)
