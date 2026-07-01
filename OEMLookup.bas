Attribute VB_Name = "OEMLookup"
' ================================================================
'  OEM Price Lookup Macro
'  How to install / update:
'    Alt+F11 → File → Import File → OEMLookup.bas
' ================================================================

Sub BuscarPreciosOEM()

    Dim scriptPath  As String
    Dim csvPath     As String
    Dim logPath     As String
    Dim wsh         As Object
    Dim result      As Integer
    Dim pythonCmd   As String

    scriptPath = ThisWorkbook.Path & "\oem_lookup.py"
    csvPath    = ThisWorkbook.Path & "\oem_results_temp.csv"
    logPath    = ThisWorkbook.Path & "\oem_log.txt"

    ' ── Verify script exists ──────────────────────────────────────
    If Dir(scriptPath) = "" Then
        MsgBox "No se encontro oem_lookup.py en:" & Chr(13) & _
               ThisWorkbook.Path, vbCritical, "OEM Lookup"
        Exit Sub
    End If

    If Not ThisWorkbook.Saved Then ThisWorkbook.Save

    ' ── Clean up previous files ───────────────────────────────────
    If Dir(csvPath) <> "" Then Kill csvPath
    If Dir(logPath) <> "" Then Kill logPath

    Application.StatusBar = "Buscando precios OEM... por favor espere."
    DoEvents

    Set wsh = CreateObject("WScript.Shell")

    ' ── Try "python" first, then "py" (Windows Python Launcher) ──
    ' Output and errors are captured to oem_log.txt for debugging
    pythonCmd = "cmd /c python """ & scriptPath & """ > """ & logPath & """ 2>&1"
    result = wsh.Run(pythonCmd, 0, True)   ' 0=hidden, True=wait

    If result <> 0 Then
        ' python failed — try "py" (Windows Python Launcher)
        If Dir(logPath) <> "" Then Kill logPath
        pythonCmd = "cmd /c py """ & scriptPath & """ > """ & logPath & """ 2>&1"
        result = wsh.Run(pythonCmd, 0, True)
    End If

    Application.StatusBar = False

    ' ── On error: show log so we can diagnose ────────────────────
    If result <> 0 Then
        Dim errMsg As String
        errMsg = "El script termino con error (codigo " & result & ")." & Chr(13) & Chr(13)

        If Dir(logPath) <> "" Then
            Dim fileNo As Integer
            Dim logLine As String
            Dim logContent As String
            fileNo = FreeFile
            Open logPath For Input As #fileNo
            Dim lineCount As Integer
            lineCount = 0
            Do While Not EOF(fileNo) And lineCount < 20
                Line Input #fileNo, logLine
                logContent = logContent & logLine & Chr(13)
                lineCount = lineCount + 1
            Loop
            Close #fileNo
            errMsg = errMsg & "--- Error detalle ---" & Chr(13) & logContent
        Else
            errMsg = errMsg & "Python no encontrado. Verifica que Python este instalado" & Chr(13) & _
                     "y que setup_oem_tool.bat se haya ejecutado correctamente."
        End If

        MsgBox errMsg, vbCritical, "OEM Lookup — Error"
        Exit Sub
    End If

    ' ── Check CSV was created ─────────────────────────────────────
    If Dir(csvPath) = "" Then
        MsgBox "El script termino bien pero no genero resultados." & Chr(13) & _
               "Verifica que haya partes sin precio en la hoja.", _
               vbInformation, "OEM Lookup"
        Exit Sub
    End If

    ' ── Read CSV and fill cells ───────────────────────────────────
    Dim ws      As Worksheet
    Dim line    As String
    Dim fields() As String
    Dim rowNum  As Long
    Dim filled  As Long

    Set ws  = ThisWorkbook.Sheets("COTIZACION")
    fileNo  = FreeFile
    filled  = 0

    Open csvPath For Input As #fileNo
    Line Input #fileNo, line   ' skip header

    Do While Not EOF(fileNo)
        Line Input #fileNo, line
        If Trim(line) = "" Then GoTo NextLine

        fields = SplitCSVLine(line)
        If UBound(fields) < 5 Then GoTo NextLine

        On Error Resume Next
        rowNum = CLng(fields(0))
        On Error GoTo 0
        If rowNum < 3 Then GoTo NextLine

        If Trim(fields(2)) <> "" Then
            ws.Cells(rowNum, 26).Value = CDbl(fields(2))
        Else
            ws.Cells(rowNum, 26).Value = ""
        End If

        If Trim(fields(3)) <> "" Then
            ws.Cells(rowNum, 27).Value = CDbl(fields(3))
        Else
            ws.Cells(rowNum, 27).Value = ""
        End If

        ws.Cells(rowNum, 28).Value = fields(4)
        ws.Cells(rowNum, 29).Value = fields(5)
        filled = filled + 1
NextLine:
    Loop
    Close #fileNo

    ' ── Column headers ───────────────────────────────────────────
    If ws.Cells(2, 26).Value = "" Then ws.Cells(2, 26).Value = "OEM_MSRP ($)"
    If ws.Cells(2, 27).Value = "" Then ws.Cells(2, 27).Value = "OEM_PRECIO ($)"
    If ws.Cells(2, 28).Value = "" Then ws.Cells(2, 28).Value = "VIN_FITS"
    If ws.Cells(2, 29).Value = "" Then ws.Cells(2, 29).Value = "OEM_URL"

    Kill csvPath
    ThisWorkbook.Save

    MsgBox "Precios OEM actualizados: " & filled & " parte(s)." & Chr(13) & Chr(13) & _
           "Revisa columnas Z-AC (OEM_MSRP, OEM_PRECIO, VIN_FITS, OEM_URL).", _
           vbInformation, "OEM Lookup"
End Sub


Private Function SplitCSVLine(line As String) As String()
    Dim result()  As String
    Dim inQuote   As Boolean
    Dim current   As String
    Dim count     As Integer
    Dim i         As Integer
    Dim c         As String

    ReDim result(0)
    count = 0: inQuote = False: current = ""

    For i = 1 To Len(line)
        c = Mid(line, i, 1)
        If c = """" Then
            inQuote = Not inQuote
        ElseIf c = "," And Not inQuote Then
            ReDim Preserve result(count)
            result(count) = current
            count = count + 1: current = ""
        Else
            current = current & c
        End If
    Next i
    ReDim Preserve result(count)
    result(count) = current
    SplitCSVLine = result
End Function
