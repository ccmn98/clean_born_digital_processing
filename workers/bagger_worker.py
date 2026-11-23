import logging
import os
import shutil
import traceback

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import bagit
from PyQt5.QtCore import QThread, pyqtSignal

import logging

logger = logging.getLogger(
    "born_digital_processing"
)

class BaggingWorker(QThread):
    print("### USING bagger_worker.py FROM:", __file__)
    
    progress_signal = pyqtSignal(str)
    
    # percentage, display message
    progress_percent_signal = pyqtSignal(int, str)
    
    # digital ID, source path, current file number, total files
    file_started_signal = pyqtSignal(str, str, int, int)
    
    # digital ID, source path, current file number, total files
    file_completed_signal = pyqtSignal(str, str, int, int)
    
    completed_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    
    def __init__(
        self,
        inputs_map: dict,              # {digital_id: path}
        output_directory: Path,
        bagger_info_dict: dict,        # from GUI
        profile_path: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.inputs_map = dict(inputs_map)
        self.output_directory = Path(output_directory)
        self.bagger_info_dict = dict(bagger_info_dict or {})
        self.profile_path = Path(profile_path) if profile_path else None
        

    def _collect_source_files(self, src_path: Path) -> list[tuple[Path, Path]]:
        """
        Return tuples of:

            source_file, relative_path

        System directories are skipped.
        """
        exclude_names = {
            "System Volume Information",
            "$RECYCLE.BIN",
            "RECYCLER",
            "RECYCLED",
            ".Spotlight-V100",
            ".Trashes",
        }
        
        files_to_copy = []
            
        for root, dirs, files in os.walk(src_path):
            root_path = Path(root)
            
            # Prevent os.walk from entering excluded directories
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in exclude_names
            ]
            
            for filename in files:
                source_file = root_path / filename
                relative_path = source_file.relative_to(src_path)

                files_to_copy.append(
                    (source_file, relative_path)
                )

        return files_to_copy
    
    def run(self):
        results = {}
        had_errors = False
        failures = []

        #self.progress_signal.emit("=== BAGGER DEBUG (worker.run) ===")
        self.progress_signal.emit(
            f"output_directory={self.output_directory}"
        )
        self.progress_signal.emit(
            f"inputs_map len={len(self.inputs_map)}"
        )

        try:
            first = next(iter(self.inputs_map.items()))
            self.progress_signal.emit(f"first item={first}")
        except StopIteration:
            self.progress_signal.emit("inputs_map is empty")

        #self.progress_signal.emit("=== END BAGGER DEBUG ===")

        try:
            bags_root = self.output_directory / "bags"
            bags_root.mkdir(parents=True, exist_ok=True)

            for digital_id, src in self.inputs_map.items():
                #self.progress_signal.emit(f"DEBUG loop: digital_id={digital_id} | src={src}")

                src_path = Path(src)
                bag_root = bags_root / digital_id

                # Fallback source if an error occurs before a file is selected
                current_source = src_path

                self.progress_signal.emit(
                    f"📦 Starting bag: {digital_id}"
                )
                logger.info("Starting bagging for %s from source: %s", digital_id, src_path)

                
                # Normalize bare Windows drive letters such as A:
                if len(str(src_path)) == 2 and str(src_path)[1] == ":":
                    src_path = Path(str(src_path) + "\\")
                    current_source = src_path

                try:
                    # --------------------------------------------------
                    # Validate source
                    # --------------------------------------------------
                    if not src_path.is_dir():
                        raise ValueError(
                            f"Unsupported input for initial ingest: "
                            f"{src_path}. This version accepts only "
                            "drives and directories."
                        )

                    # --------------------------------------------------
                    # Remove an existing partial/output bag
                    # --------------------------------------------------
                    if bag_root.exists():
                        shutil.rmtree(
                            bag_root,
                            ignore_errors=True
                        )

                    bag_root.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    # --------------------------------------------------
                    # Create initial BagIt structure
                    # --------------------------------------------------
                    metadata = OrderedDict(
                        self.bagger_info_dict
                    )
                    metadata["Digital-ID"] = digital_id
                    metadata["Bagging-Date"] = (
                        datetime.now().strftime("%Y-%m-%d")
                    )

                    bagit.make_bag(
                        str(bag_root),
                        metadata,
                        checksums=["md5"]
                    )

                    data_dir = bag_root / "data"
                    data_dir.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    # --------------------------------------------------
                    # Discover payload files
                    # --------------------------------------------------
                    self.progress_signal.emit(
                        f"🔎 Discovering files for {digital_id}"
                    )

                    self.progress_percent_signal.emit(
                        0,
                        f"Discovering files for {digital_id}"
                    )

                    files_to_copy = self._collect_source_files(
                        src_path
                    )
                    total_files = len(files_to_copy)

                    self.progress_signal.emit(
                        f"📋 {digital_id}: "
                        f"{total_files} files found"
                    )

                    if total_files == 0:
                        self.progress_percent_signal.emit(
                            100,
                            f"No files found for {digital_id}"
                        )

                    # --------------------------------------------------
                    # Copy each payload file
                    # --------------------------------------------------
                    for file_number, (
                        source_file,
                        relative_path
                    ) in enumerate(
                        files_to_copy,
                        start=1
                    ):
                        current_source = source_file
                        target = data_dir / relative_path

                        target.parent.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        percent_before = int(
                            (
                                (file_number - 1)
                                / total_files
                            )
                            * 100
                        )

                        self.file_started_signal.emit(
                            digital_id,
                            str(source_file),
                            file_number,
                            total_files
                        )

                        self.progress_percent_signal.emit(
                            percent_before,
                            (
                                f"Copying {source_file.name} "
                                f"({file_number} of "
                                f"{total_files})"
                            )
                        )

                        # self.progress_signal.emit(
                        #     (
                        #         f"▶ Copying: {source_file} "
                        #         f"({file_number} of "
                        #         f"{total_files})"
                        #     )
                        # )

                        #print((f"DEBUG: copying "f"{source_file} to {target}"),flush=True)

                        shutil.copy2(
                            source_file,
                            target
                        )

                        percent_after = int(
                            (
                                file_number
                                / total_files
                            )
                            * 100
                        )

                        self.file_completed_signal.emit(
                            digital_id,
                            str(source_file),
                            file_number,
                            total_files
                        )

                        self.progress_percent_signal.emit(
                            percent_after,
                            (
                                f"Copied {source_file.name} "
                                f"({file_number} of "
                                f"{total_files})"
                            )
                        )

                        # self.progress_signal.emit(
                        #     f"✅ Copied: {source_file}"
                        # )

                    # --------------------------------------------------
                    # Calculate payload totals
                    # --------------------------------------------------
                    self.progress_signal.emit(
                        f"🔢 Calculating payload totals "
                        f"for {digital_id}"
                    )

                    total_bytes = 0
                    file_count = 0

                    for root, _, files in os.walk(data_dir):
                        for filename in files:
                            payload_file = (
                                Path(root) / filename
                            )
                            total_bytes += (
                                payload_file.stat().st_size
                            )
                            file_count += 1

                    metadata["Bag-Size"] = (
                        f"{total_bytes / 1024:.1f} KB"
                    )
                    metadata["Payload-Oxum"] = (
                        f"{total_bytes}.{file_count}"
                    )

                    # --------------------------------------------------
                    # Generate and save BagIt manifests
                    # --------------------------------------------------
                    self.progress_signal.emit(
                        f"🧾 Generating manifests for "
                        f"{digital_id}"
                    )

                    bag = bagit.Bag(str(bag_root))
                    bag.save(manifests=True)

                    baginfo_path = (
                        bag_root / "bag-info.txt"
                    )

                    with baginfo_path.open(
                        "w",
                        encoding="utf-8"
                    ) as baginfo_file:
                        for key, value in metadata.items():
                            baginfo_file.write(
                                f"{key}: {value}\n"
                            )

                    # Recalculate tag manifest after changing bag-info
                    bag = bagit.Bag(str(bag_root))
                    bag.save(manifests=True)

                    results[digital_id] = str(bag_root)

                    self.progress_signal.emit(
                        f"✅ Completed bag: {digital_id}"
                    )

                except OSError as e:
                    had_errors = True
                    failed_source = current_source

                    error_message = (
                        "❌ BAGGING I/O ERROR\n"
                        f"Digital ID: {digital_id}\n"
                        f"Source: {failed_source}\n"
                        f"Error type: "
                        f"{type(e).__name__}\n"
                        f"Windows error: {e}\n\n"
                        "Bag creation was aborted because "
                        "the source could not be read "
                        "completely."
                    )

                    failures.append({
                        "digital_id": digital_id,
                        "source": str(failed_source),
                        "error": str(e),
                    })

                    print(
                        error_message,
                        flush=True
                    )
                    logger.error(error_message)

                    if bag_root.exists():
                        shutil.rmtree(
                            bag_root,
                            ignore_errors=True
                        )

                    self.error_signal.emit(
                        error_message
                    )

                    # Continue with the next selected source
                    continue

                except Exception as e:
                    had_errors = True

                    error_message = (
                        "❌ BAGGING ERROR\n"
                        f"Digital ID: {digital_id}\n"
                        f"Source: {current_source}\n"
                        f"Error type: "
                        f"{type(e).__name__}\n"
                        f"Error: {e}\n\n"
                        "Traceback:\n"
                        f"{traceback.format_exc()}"
                    )

                    failures.append({
                        "digital_id": digital_id,
                        "source": str(current_source),
                        "error": str(e),
                    })

                    print(
                        error_message,
                        flush=True
                    )
                    logger.exception(
                        error_message
                    )

                    if bag_root.exists():
                        shutil.rmtree(
                            bag_root,
                            ignore_errors=True
                        )

                    self.error_signal.emit(
                        error_message
                    )

                    # Continue with the next selected source
                    continue

            # ------------------------------------------------------
            # All selected sources have now been attempted
            # ------------------------------------------------------
            summary = {
                "results": results,
                "had_errors": had_errors,
                "failures": failures,
            }

            self.completed_signal.emit(summary)

        except Exception as e:
            error_message = (
                "❌ UNEXPECTED BAGGING WORKER FAILURE\n"
                f"Error type: {type(e).__name__}\n"
                f"Error: {e}\n\n"
                "Traceback:\n"
                f"{traceback.format_exc()}"
            )

            print(
                error_message,
                flush=True
            )
            logger.exception(
                error_message
            )
            self.error_signal.emit(
                error_message
            )

    