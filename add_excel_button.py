"""
add_excel_button.py
===================
Adds a "Buscar Precios OEM" button to cotizacion_bulk.xlsm and installs
the VBA macro that runs oem_lookup.py when clicked.

Run this ONCE:
    python add_excel_button.py

Requirements: pip install pywin32
(setup_oem_tool.bat will install this for you)
"""

import sys
import os

# ── Check pywin32 is available ────────────────────────────────────────────────
try:
    import win32com.client as win32
except ImportError:
    print("Installing pywin32...")
    os.system("pip install pywin32 --quiet")
    try:
        import win32com.client as win32
    except ImportError:
        print("\nERROR: Could not install pywin32.")
        print("Please run:  pip install pywin32")
        input("\nPress Enter to exit...")
        sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE  = os.path.join(SCRIPT_DIR, 'cotizacion_bulk.xlsm')
OEM_SCRIPT  = os.path.join(SCRIPT_DIR, 'oem_lookup.py')

# ── VBA code ─────────────────────────────────────────────────────────────────
# Uses ThisWorkbook.Path so it works regardless of folder location.
VBA_CODE = r"""
' ─────────────────────────────────────────────────────────────────
'  OEM Price Lookup — runs oem_lookup.py via Python
'  Installed automatically by add_excel_button.py
' ─────────────────────────────────────────────────────────────────

Sub BuscarPreciosOEM()
    Dim scriptPath  As String
    Dim pythonCmd   As String
    Dim wsh         As Object
    Dim result      As Integer

    scriptPath = ThisWorkbook.Path & "\oem_lookup.py"

    ' Verify script exists
    If Dir(scriptPath) = "" Then
        MsgBox "No se encontro oem_lookup.py en:" & Chr(13) & _
               ThisWorkbook.Path & Chr(13) & Chr(13) & _
               "Asegurate de que oem_lookup.py este en la misma carpeta.", _
               vbCritical, "OEM Lookup"
        Exit Sub
    End If

    ' Save the workbook before running
    If Not ThisWorkbook.Saved Then
        ThisWorkbook.Save
    End If

    Application.StatusBar = "Buscando precios OEM... por favor espere (puede tomar varios minutos)."
    DoEvents

    ' Run Python script and wait for it to finish
    pythonCmd = "python """ & scriptPath & """"
    Set wsh = CreateObject("WScript.Shell")
    result = wsh.Run(pythonCmd, 1, True)   ' 1=normal window, True=wait for exit

    Application.StatusBar = False

    Select Case result
        Case 0
            ' Reload the workbook to show updated values
            Application.StatusBar = "Recargando datos..."
            DoEvents
            Dim fullPath As String
            fullPath = ThisWorkbook.FullName
            ThisWorkbook.Close SaveChanges:=False
            Workbooks.Open Filename:=fullPath
            Application.StatusBar = False
            MsgBox "Precios OEM actualizados correctamente." & Chr(13) & _
                   "Revisa las columnas Z-AC (OEM_MSRP, OEM_PRECIO, etc.)", _
                   vbInformation, "OEM Lookup"
        Case Else
            MsgBox "El script termino con codigo de error: " & result & Chr(13) & Chr(13) & _
                   "Posibles causas:" & Chr(13) & _
                   "  - Python no esta instalado" & Chr(13) & _
                   "  - Playwright no esta instalado (ejecuta setup_oem_tool.bat)", _
                   vbExclamation, "OEM Lookup — Error"
    End Select
End Sub
"""

# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: Cannot find {EXCEL_FILE}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    if not os.path.exists(OEM_SCRIPT):
        print(f"WARNING: oem_lookup.py not found at {OEM_SCRIPT}")
        print("The button will be added, but make sure oem_lookup.py is in the same folder.")

    print("Opening Excel (hidden)...")
    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb = excel.Workbooks.Open(EXCEL_FILE)
    except Exception as e:
        print(f"ERROR: Could not open {EXCEL_FILE}")
        print(f"Detail: {e}")
        print("Make sure the file is CLOSED in Excel before running this.")
        excel.Quit()
        input("\nPress Enter to exit...")
        sys.exit(1)

    ws = wb.Sheets("COTIZACION")

    # ── Check VBA project access ──────────────────────────────────────────────
    try:
        vbp = wb.VBProject
        _ = vbp.VBComponents.Count  # triggers access check
    except Exception:
        print(
            "\n" + "="*60 + "\n"
            "ACTION REQUIRED — Enable VBA Project Access in Excel:\n\n"
            "  1. Open Excel\n"
            "  2. File → Options → Trust Center → Trust Center Settings\n"
            "  3. Macro Settings tab\n"
            "  4. Check: 'Trust access to the VBA project object model'\n"
            "  5. Click OK, close Excel, then re-run this script.\n"
            + "="*60
        )
        wb.Close(SaveChanges=False)
        excel.Quit()
        input("\nPress Enter to exit...")
        sys.exit(1)

    # ── Add / replace VBA module ──────────────────────────────────────────────
    MODULE_NAME = "OEMLookupModule"
    try:
        for comp in vbp.VBComponents:
            if comp.Name == MODULE_NAME:
                vbp.VBComponents.Remove(comp)
                break
        module = vbp.VBComponents.Add(1)   # 1 = vbext_ct_StdModule
        module.Name = MODULE_NAME
        module.CodeModule.AddFromString(VBA_CODE)
        print("✓ VBA module installed.")
    except Exception as e:
        print(f"ERROR adding VBA module: {e}")
        wb.Close(SaveChanges=False)
        excel.Quit()
        input("\nPress Enter to exit...")
        sys.exit(1)

    # ── Add button to COTIZACION sheet ────────────────────────────────────────
    BTN_NAME = "OEMLookupBtn"
    try:
        for shape in ws.Shapes:
            if shape.Name == BTN_NAME:
                shape.Delete()
                break

        # Position: top-right area, above data  (Left, Top, Width, Height in points)
        btn = ws.Buttons.Add(500, 4, 190, 28)
        btn.Name = BTN_NAME
        btn.Caption = "Buscar Precios OEM"
        btn.OnAction = "BuscarPreciosOEM"

        # Style the button text
        with btn.Characters(1, len(btn.Caption)).Font as f:
            f.Bold = True
            f.Size = 10

        print("✓ Button added to COTIZACION sheet.")
    except Exception as e:
        print(f"WARNING: Could not add button: {e}")
        print("The macro is installed — you can run it manually from the VBA editor (Alt+F8).")

    # ── Save and close ────────────────────────────────────────────────────────
    wb.Save()
    wb.Close()
    excel.Quit()

    print("\n" + "="*50)
    print(" Done! Open cotizacion_bulk.xlsm and click")
    print(" the  [Buscar Precios OEM]  button.")
    print("="*50)


if __name__ == "__main__":
    main()
