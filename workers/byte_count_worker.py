from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from PyQt5.QtCore import QThread, pyqtSignal

EXCLUDED_FILES = {
    "bag-info.txt",
    "bagit.txt",
    "manifest-md5.txt",
    "tagmanifest-md5.txt",
    }

class ByteCountWorker(QThread):
    progress_signal = pyqtSignal(str)
    current_path_signal = pyqtSignal(str)
    completed_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        inputs_map: dict[str, str],
        output_directory: str | Path,
        parent=None,
    ):
        super().__init__(parent)

        self.inputs_map = dict(inputs_map)
        self.output_directory = Path(output_directory)

        self.wb = None
        self.summary_ws = None
        self.dir_ws = None
        self.file_ws = None

    def run(self):
        try:
            if not self.inputs_map:
                raise ValueError("No input directories were provided.")

            self._create_workbook()

            processed_objects = 0
            matched_bags = 0
            mismatched_bags = 0
            unavailable_oxum = 0

            for digital_id, source_path in self.inputs_map.items():
                source_path = os.path.abspath(source_path)

                self.current_path_signal.emit(source_path)
                self.progress_signal.emit(
                    f"Starting byte count: {digital_id} → {source_path}"
                )

                if not os.path.isdir(source_path):
                    self.progress_signal.emit(
                        f"Skipped missing or invalid directory: {source_path}"
                    )
                    continue

                results = self.process_collection(
                    source_path,
                    digital_id,
                )

                processed_objects += results["processed_objects"]
                matched_bags += results["matched_bags"]
                mismatched_bags += results["mismatched_bags"]
                unavailable_oxum += results["unavailable_oxum"]

            report_path = self._save_workbook()

            self.completed_signal.emit({
                "report_path": str(report_path),
                "processed_objects": processed_objects,
                "matched_bags": matched_bags,
                "mismatched_bags": mismatched_bags,
                "unavailable_oxum": unavailable_oxum,
            })

        except Exception as error:
            self.error_signal.emit(
                f"Byte count failed: {type(error).__name__}: {error}"
            )

    def _create_workbook(self):
        self.wb = openpyxl.Workbook()

        self.summary_ws = self.wb.active
        self.summary_ws.title = "Summary"

        self.dir_ws = self.wb.create_sheet("Directory Totals")
        self.file_ws = self.wb.create_sheet("File Details")

        self.summary_ws.append([
            "Digital ID",
            "Object Name",
            "Type",
            "Path",
            "Payload Path",
            "Stored Payload Bytes",
            "Stored Payload File Count",
            "Stored Payload-Oxum",
            "Calculated Payload Bytes",
            "Calculated Payload File Count",
            "Calculated Payload-Oxum",
            "Byte Difference",
            "File Count Difference",
            "Payload-Oxum Result",
        ])

        self.dir_ws.append([
            "Digital ID",
            "Object Name",
            "Object Type",
            "Directory Path",
            "Relative Directory",
            "Directory Bytes",
            "File Count",
        ])

        self.file_ws.append([
            "Digital ID",
            "Object Name",
            "Object Type",
            "File Name",
            "File Path",
            "Relative File Path",
            "File Bytes",
        ])

    @staticmethod
    def is_bag_directory(path: str) -> bool:
        return (
            os.path.isdir(os.path.join(path, "data"))
            and os.path.isfile(os.path.join(path, "bagit.txt"))
        )

    def find_bag_directories(self, collection_path: str) -> list[str]:
        bag_paths = []

        for root, dirnames, filenames in os.walk(
            collection_path,
            onerror=self._walk_error,
        ):
            if self.is_bag_directory(root):
                bag_paths.append(os.path.normpath(root))

                # Do not descend into a bag after finding its root.
                dirnames[:] = []

        return bag_paths

    @staticmethod
    def read_payload_oxum(
        bag_path: str,
    ) -> tuple[Optional[int], Optional[int]]:
        bag_info_path = os.path.join(bag_path, "bag-info.txt")

        if not os.path.isfile(bag_info_path):
            return None, None

        try:
            with open(
                bag_info_path,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as bag_info:
                for line in bag_info:
                    if line.lower().startswith("payload-oxum:"):
                        value = line.split(":", 1)[1].strip()
                        byte_text, file_text = value.split(".", 1)

                        return int(byte_text), int(file_text)

        except (OSError, ValueError):
            return None, None

        return None, None

    def process_collection(
        self,
        collection_path: str,
        digital_id: str,
    ) -> dict:
        results = {
            "processed_objects": 0,
            "matched_bags": 0,
            "mismatched_bags": 0,
            "unavailable_oxum": 0,
        }

        if self.is_bag_directory(collection_path):
            bag_result = self.process_bag_directory(
                collection_path,
                digital_id,
            )
            results["processed_objects"] += 1
            results[bag_result] += 1
            return results

        bag_paths = self.find_bag_directories(collection_path)

        self.process_regular_directory(
            collection_path,
            digital_id,
            bag_paths,
        )
        results["processed_objects"] += 1

        for bag_path in bag_paths:
            bag_result = self.process_bag_directory(
                bag_path,
                digital_id,
            )

            results["processed_objects"] += 1
            results[bag_result] += 1

        return results

    def process_bag_directory(
        self,
        bag_path: str,
        digital_id: str,
    ) -> str:
        bag_name = os.path.basename(os.path.normpath(bag_path))
        payload_path = os.path.join(bag_path, "data")

        self.progress_signal.emit(
            f"Counting BagIt payload: {bag_name}"
        )
        self.current_path_signal.emit(payload_path)

        expected_bytes, expected_files = self.read_payload_oxum(
            bag_path
        )

        total_size = 0
        file_count = 0
        directory_sizes = {}
        directory_file_counts = {}

        for data_root, data_dirs, data_files in os.walk(
            payload_path,
            topdown=False,
            onerror=self._walk_error,
        ):
            directory_total = 0
            directory_count = 0

            for filename in data_files:
                file_path = os.path.join(data_root, filename)
                if os.path.islink(file_path):
                    continue

                try:
                    size = os.path.getsize(file_path)
                except OSError as error:
                    self.progress_signal.emit(
                        f"Could not read {file_path}: {error}"
                    )
                    continue

                total_size += size
                file_count += 1
                directory_total += size
                directory_count += 1

                relative_file_path = os.path.relpath(
                    file_path,
                    payload_path,
                )

                self.file_ws.append([
                    digital_id,
                    bag_name,
                    "BagIt Bag",
                    filename,
                    file_path,
                    relative_file_path,
                    size,
                ])

            for dirname in data_dirs:
                subdirectory = os.path.join(data_root, dirname)
                directory_total += directory_sizes.get(
                    subdirectory,
                    0,
                )
                directory_count += directory_file_counts.get(subdirectory, 0)

            directory_sizes[data_root] = directory_total
            directory_file_counts[data_root] = directory_count

        for directory, size in sorted(directory_sizes.items()):
            self.dir_ws.append([
                digital_id,
                bag_name,
                "BagIt Bag",
                directory,
                os.path.relpath(directory, payload_path),
                size,
                directory_file_counts[directory],
            ])

        calculated_oxum = f"{total_size}.{file_count}"

        if expected_bytes is None or expected_files is None:
            stored_oxum = ""
            byte_difference = None
            file_difference = None
            comparison_result = "Payload-Oxum unavailable"
            result_key = "unavailable_oxum"

        else:
            stored_oxum = f"{expected_bytes}.{expected_files}"
            byte_difference = total_size - expected_bytes
            file_difference = file_count - expected_files

            if byte_difference == 0 and file_difference == 0:
                comparison_result = "MATCH"
                result_key = "matched_bags"
            elif byte_difference != 0 and file_difference != 0:
                comparison_result = (
                    "BYTE AND FILE COUNT MISMATCH"
                )
                result_key = "mismatched_bags"
            elif byte_difference != 0:
                comparison_result = "BYTE COUNT MISMATCH"
                result_key = "mismatched_bags"
            else:
                comparison_result = "FILE COUNT MISMATCH"
                result_key = "mismatched_bags"

        self.summary_ws.append([
            digital_id,
            bag_name,
            "BagIt Bag",
            bag_path,
            payload_path,
            expected_bytes,
            expected_files,
            stored_oxum,
            total_size,
            file_count,
            calculated_oxum,
            byte_difference,
            file_difference,
            comparison_result,
        ])

        self.progress_signal.emit(
            f"{bag_name}: {comparison_result}; "
            f"{total_size:,} bytes; {file_count:,} files"
        )

        return result_key

    def process_regular_directory(
        self,
        dir_path: str,
        digital_id: str,
        bag_paths: list[str],
    ):
        object_name = os.path.basename(
            os.path.normpath(dir_path)
        )

        normalized_bags = {
            os.path.normcase(os.path.normpath(path))
            for path in bag_paths
        }

        total_size = 0
        file_count = 0
        directory_sizes = {}
        directory_file_counts = {}

        for root, dirnames, filenames in os.walk(
            dir_path,
            topdown=False,
            onerror=self._walk_error,
        ):
            normalized_root = os.path.normcase(
                os.path.normpath(root)
            )

            if any(
                os.path.commonpath([normalized_root, bag_path])
                == bag_path
                for bag_path in normalized_bags
            ):
                continue

            directory_total = 0
            directory_count = 0

            for filename in filenames:
                file_path = os.path.join(root, filename)
                if filename.lower() in EXCLUDED_FILES:
                    continue

                if os.path.islink(file_path):
                    continue


                try:
                    size = os.path.getsize(file_path)
                except OSError as error:
                    self.progress_signal.emit(
                        f"Could not read {file_path}: {error}"
                    )
                    continue

                total_size += size
                file_count += 1
                directory_total += size
                directory_count += 1

                self.file_ws.append([
                    digital_id,
                    object_name,
                    "Regular Directory",
                    filename,
                    file_path,
                    os.path.relpath(file_path, dir_path),
                    size,
                ])

            for dirname in dirnames:
                subdirectory = os.path.join(root, dirname)
                normalized_subdirectory = os.path.normcase(
                    os.path.normpath(subdirectory)
                )

                if normalized_subdirectory in normalized_bags:
                    continue

                directory_total += directory_sizes.get(
                    subdirectory,
                    0,
                )
                directory_count += directory_file_counts.get(subdirectory, 0)

            directory_sizes[root] = directory_total
            directory_file_counts[root] = directory_count

        for directory, size in sorted(directory_sizes.items()):
            self.dir_ws.append([
                digital_id,
                object_name,
                "Regular Directory",
                directory,
                os.path.relpath(directory, dir_path),
                size,
                directory_file_counts[directory],
            ])

        self.summary_ws.append([
            digital_id,
            object_name,
            "Regular Directory",
            dir_path,
            "",
            None,
            None,
            "",
            total_size,
            file_count,
            "",
            None,
            None,
            "Not applicable",
        ])

        self.progress_signal.emit(
            f"{object_name}: {total_size:,} bytes; "
            f"{file_count:,} files"
        )

    def _walk_error(self, error: OSError):
        self.progress_signal.emit(f"Directory scan error: {error}")

    def _format_workbook(self):
        for worksheet in (
            self.summary_ws,
            self.dir_ws,
            self.file_ws,
        ):
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for cell in worksheet[1]:
                cell.font = Font(bold=True)

            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(
                    column[0].column
                )

                for cell in column:
                    if cell.value is not None:
                        max_length = max(
                            max_length,
                            len(str(cell.value)),
                        )

                worksheet.column_dimensions[
                    column_letter
                ].width = min(max_length + 2, 60)

        byte_headers = {
            "Stored Payload Bytes",
            "Calculated Payload Bytes",
            "Byte Difference",
            "Directory Bytes",
            "File Bytes",
            "File Count",
            "Stored Payload File Count",
            "Calculated Payload File Count",
            "File Count Difference",
        }

        for worksheet in (
            self.summary_ws,
            self.dir_ws,
            self.file_ws,
        ):
            for column_index, cell in enumerate(
                worksheet[1],
                start=1,
            ):
                if cell.value in byte_headers:
                    for row in range(
                        2,
                        worksheet.max_row + 1,
                    ):
                        worksheet.cell(
                            row=row,
                            column=column_index,
                        ).number_format = "#,##0"

    def _save_workbook(self) -> Path:
        report_directory = self.output_directory / "reports"
        report_directory.mkdir(parents=True, exist_ok=True)

        output_path = report_directory / "byte_count_report.xlsx"

        self._format_workbook()

        try:
            self.wb.save(output_path)
        except PermissionError as error:
            raise PermissionError(
                "Could not save byte_count_report.xlsx. "
                "Close the report if it is already open in Excel."
            ) from error

        return output_path