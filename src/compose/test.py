import os
import re
from pathlib import Path
from collections import defaultdict

def remove_duplicate_drafts(drafts_folder):
    """
    Find files with same job ID prefix, keep the oldest file, delete duplicates.
    """
    drafts_path = Path(drafts_folder)
    
    if not drafts_path.exists():
        print(f"Error: Folder '{drafts_folder}' does not exist")
        return
    
    # Group files by job ID prefix
    file_groups = defaultdict(list)
    
    # Pattern to match: number_rest_of_name_date.md
    pattern = r'^(\d+)_.*?\.md$'
    
    for file_path in drafts_path.glob("*.md"):
        match = re.match(pattern, file_path.name)
        if match:
            job_id = match.group(1)
            file_groups[job_id].append(file_path)
    
    # Process each group
    deleted_count = 0
    kept_count = 0
    
    for job_id, files in file_groups.items():
        if len(files) > 1:
            print(f"\n📁 Job ID {job_id} has {len(files)} files:")
            
            # Sort by modification time (oldest first)
            files_sorted = sorted(files, key=lambda x: x.stat().st_mtime)
            
            # Keep the oldest file
            file_to_keep = files_sorted[0]
            files_to_delete = files_sorted[1:]
            
            print(f"   ✅ Keeping: {file_to_keep.name} (oldest)")
            kept_count += 1
            
            # Delete duplicates
            for file_to_delete in files_to_delete:
                try:
                    file_to_delete.unlink()  # Delete the file
                    print(f"   🗑️  Deleting: {file_to_delete.name}")
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ Error deleting {file_to_delete.name}: {e}")
        else:
            # Only one file in group, no action needed
            kept_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Files kept: {kept_count}")
    print(f"   Files deleted: {deleted_count}")
    print(f"   Total files processed: {kept_count + deleted_count}")

def main():
    # Set the path to your drafts folder
    drafts_folder = "data/drafts"  # Adjust this path if needed
    
    print("🔍 Scanning for duplicate draft files...")
    remove_duplicate_drafts(drafts_folder)

if __name__ == "__main__":
    main()