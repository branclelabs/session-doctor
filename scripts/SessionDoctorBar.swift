// Session Doctor — single menu-bar app. No Dock icon, no terminal, ever.
//
// Lives in the menu bar, polls scripts/doctor.sh for state, and offers:
// status · Open Dashboard · Start/Stop · Show Log · Quit & Stop Server.
// PROJECT_DIR is baked in by scripts/build-app.sh (%%PROJECT_DIR%%), with a
// sibling-folder fallback so the app keeps working if moved with the project.
import AppKit
import Foundation

let kBakedProjectDir = "%%PROJECT_DIR%%"

func projectDir() -> String {
    let fm = FileManager.default
    if fm.fileExists(atPath: kBakedProjectDir + "/scripts/doctor.sh") {
        return kBakedProjectDir
    }
    let sib = (Bundle.main.bundlePath as NSString).deletingLastPathComponent
    if fm.fileExists(atPath: (sib as NSString).appendingPathComponent("scripts/doctor.sh")) {
        return sib
    }
    return kBakedProjectDir
}

func runDoctor(_ args: String..., timeout: TimeInterval = 25, completion: ((Int32, String) -> Void)? = nil) {
    DispatchQueue.global(qos: .userInitiated).async {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [projectDir() + "/scripts/doctor.sh"] + args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        // Watchdog: a hung helper must never wedge the UI or pile up.
        let watchdog = DispatchWorkItem {
            if p.isRunning { p.terminate() }
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: watchdog)
        var out: String
        var code: Int32
        do {
            try p.run()
            p.waitUntilExit()
            code = p.terminationStatus
            out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        } catch {
            code = -1
            out = "could not launch helper"
        }
        watchdog.cancel()
        // Distinguish watchdog kills (SIGTERM=15) from real failures.
        let finalOut = (code == 15) ? "helper timed out after \(Int(timeout))s" : out.trimmingCharacters(in: .whitespacesAndNewlines)
        let c = code, o = finalOut
        DispatchQueue.main.async { completion?(c, o) }
    }
}

func pulseIcon(running: Bool) -> NSImage {
    let size = NSSize(width: 22, height: 22)
    let img = NSImage(size: size)
    img.lockFocus()
    NSColor.clear.set()
    NSBezierPath.fill(NSRect(origin: .zero, size: size))
    // emerald pulse line (matches the web favicon)
    let pulse = NSBezierPath()
    pulse.move(to: NSPoint(x: 1, y: 11))
    pulse.line(to: NSPoint(x: 5, y: 11))
    pulse.line(to: NSPoint(x: 7.5, y: 5))
    pulse.line(to: NSPoint(x: 11.5, y: 17))
    pulse.line(to: NSPoint(x: 14, y: 11))
    pulse.line(to: NSPoint(x: 17.5, y: 11))
    pulse.lineWidth = 1.8
    pulse.lineCapStyle = .round
    pulse.lineJoinStyle = .round
    NSColor(red: 0.06, green: 0.73, blue: 0.51, alpha: 1).setStroke()
    pulse.stroke()
    // status dot: green = running, dim = stopped
    let dot = NSBezierPath(ovalIn: NSRect(x: 17, y: 15, width: 5, height: 5))
    (running ? NSColor.systemGreen : NSColor.tertiaryLabelColor).setFill()
    dot.fill()
    img.unlockFocus()
    img.isTemplate = false
    return img
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var statusMenuItem: NSMenuItem!
    var openItem: NSMenuItem!
    var toggleItem: NSMenuItem!
    var isRunning = false
    var didAutoStart = false
    var autoAttempts = 0
    var userStopped = false
    var starting = false
    var succeededOnce = false

    func appLog(_ msg: String) {
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(msg)\n"
        let url = URL(fileURLWithPath: projectDir() + "/logs/session-doctor-menu.log")
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let h = try? FileHandle(forWritingTo: url) {
            h.seekToEndOfFile()
            h.write(Data(line.utf8))
            try? h.close()
        } else {
            try? Data(line.utf8).write(to: url)
        }
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = pulseIcon(running: false)

        let menu = NSMenu()
        statusMenuItem = NSMenuItem(title: "Checking…", action: nil, keyEquivalent: "")
        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)
        menu.addItem(.separator())
        openItem = NSMenuItem(title: "Open Dashboard", action: #selector(openDashboard), keyEquivalent: "o")
        openItem.target = self
        menu.addItem(openItem)
        toggleItem = NSMenuItem(title: "Start Server", action: #selector(toggleServer), keyEquivalent: "s")
        toggleItem.target = self
        menu.addItem(toggleItem)
        let logItem = NSMenuItem(title: "Show Log", action: #selector(showLog), keyEquivalent: "l")
        logItem.target = self
        menu.addItem(logItem)
        menu.addItem(.separator())
        let quitItem = NSMenuItem(title: "Quit & Stop Server", action: #selector(quitAndStop), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
        statusItem.menu = menu

        refresh()
        Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func refresh() {
        runDoctor("status") { [weak self] _, out in
            guard let self else { return }
            let running = out.hasPrefix("RUNNING") || out.hasPrefix("ALREADY")
            let wasStopped = !self.isRunning
            if running != self.isRunning {
                self.appLog("state -> \(running ? "running" : "stopped")")
            }
            self.isRunning = running
            self.statusItem.button?.image = pulseIcon(running: running)
            // First launch builds the runtime in the background (marker file
            // written by doctor.sh) — say so instead of flashing "Stopped".
            let bootstrapping = FileManager.default.fileExists(
                atPath: projectDir() + "/.session-doctor.bootstrap")
            if bootstrapping && !running {
                self.statusMenuItem.title = "Setting up first launch…"
            } else if running {
                let url = out.split(separator: " ").last.map(String.init) ?? ""
                self.statusMenuItem.title = "Running · \(url)"
            } else {
                self.statusMenuItem.title = "Stopped"
            }
            self.openItem.isEnabled = running
            self.toggleItem.title = running ? "Stop Server" : "Start Server"
            if running { self.succeededOnce = true }
            // Launch behaves like the old double-click app (boot + open), with
            // a few retries in case the first attempt races a dying process.
            // Stops retrying after success, after 5 tries, or once the user
            // explicitly hits Stop.
            if !self.didAutoStart {
                self.didAutoStart = true
                if wasStopped && !running {
                    self.appLog("autostart attempt 1")
                    self.startServer(openAfter: true)
                }
            } else if !running && !self.userStopped && !self.starting && !self.succeededOnce && self.autoAttempts < 5 {
                self.autoAttempts += 1
                self.appLog("autostart retry \(self.autoAttempts)")
                self.startServer(openAfter: false)
            }
        }
    }

    func startServer(openAfter: Bool) {
        guard !starting else { return }
        starting = true
        toggleItem.isEnabled = false
        statusMenuItem.title = "Starting…"
        appLog("start requested (openAfter=\(openAfter))")
        // Long leash: a first launch includes the one-time build, which
        // takes minutes. doctor.sh exits early on health; this only bounds
        // a truly wedged helper.
        runDoctor("start", timeout: 660) { [weak self] code, out in
            guard let self else { return }
            self.starting = false
            self.toggleItem.isEnabled = true
            self.appLog("start done code=\(code) out=\(out.split(separator: "\n").first ?? "")")
            if out.hasPrefix("STARTED") || out.hasPrefix("ALREADY") {
                self.userStopped = false
                self.refresh()
                if openAfter { self.openDashboard() }
            } else {
                self.refresh()
                self.alert(title: "Session Doctor could not start.",
                           body: out.isEmpty ? "No details. Try Show Log." : out,
                           buttons: ["Show Log", "OK"]) { resp in
                    if resp == "Show Log" { self.showLog() }
                }
            }
        }
    }

    @objc func openDashboard() {
        runDoctor("open") { [weak self] code, out in
            if code != 0 {
                self?.alert(title: "Dashboard is not running.",
                            body: "Start the server first, then open the dashboard.",
                            buttons: ["OK"], handler: nil)
            }
        }
    }

    @objc func toggleServer() {
        if isRunning {
            userStopped = true
            toggleItem.isEnabled = false
            statusMenuItem.title = "Stopping…"
            appLog("stop requested")
            runDoctor("stop") { [weak self] _, out in
                guard let self else { return }
                self.toggleItem.isEnabled = true
                self.appLog("stop done out=\(out.split(separator: "\n").first ?? "")")
                self.refresh()
            }
        } else {
            userStopped = false
            startServer(openAfter: true)
        }
    }

    @objc func showLog() {
        let log = (projectDir() as NSString).appendingPathComponent("logs/session-doctor.log")
        if FileManager.default.fileExists(atPath: log) {
            NSWorkspace.shared.open(URL(fileURLWithPath: log))
        } else {
            alert(title: "No log yet.", body: "Start the server once and the log will appear here.", buttons: ["OK"], handler: nil)
        }
    }

    @objc func quitAndStop() {
        NSApp.terminate(nil)
    }

    // Single choke point for ALL quits (menu, ⌘Q, Dock, osascript, logout):
    // the server always goes down with the app.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if !isRunning {
            appLog("quit (server already stopped)")
            return .terminateNow
        }
        let a = NSAlert()
        a.messageText = "Stop the server and quit?"
        a.informativeText = "The dashboard will go offline. If a fix is running in the browser, let it finish first."
        a.alertStyle = .warning
        a.addButton(withTitle: "Stop & Quit")
        a.addButton(withTitle: "Cancel")
        guard a.runModal() == .alertFirstButtonReturn else { return .terminateCancel }
        appLog("quit requested, stopping server first")
        runDoctor("stop") { [weak self] _, out in
            self?.appLog("quit-time stop done out=\(out.split(separator: "\n").first ?? "")")
            if (out.hasPrefix("STOPPED")) {
                NSApp.reply(toApplicationShouldTerminate: true)
            } else {
                self?.alert(title: "Could not stop the server.",
                            body: String(out.prefix(300)),
                            buttons: ["Stay Open"]) { _ in }
                NSApp.reply(toApplicationShouldTerminate: false)
            }
        }
        return .terminateLater
    }

    func alert(title: String, body: String, buttons: [String], handler: ((String) -> Void)?) {
        let a = NSAlert()
        a.messageText = title
        a.informativeText = body
        for b in buttons { a.addButton(withTitle: b) }
        a.alertStyle = .warning
        if let win = statusItem.button?.window {
            a.beginSheetModal(for: win) { resp in
                let idx = resp.rawValue - NSApplication.ModalResponse.alertFirstButtonReturn.rawValue
                handler?(idx >= 0 && idx < buttons.count ? buttons[idx] : "")
            }
        } else {
            let resp = a.runModal()
            let idx = resp.rawValue - NSApplication.ModalResponse.alertFirstButtonReturn.rawValue
            handler?(idx >= 0 && idx < buttons.count ? buttons[idx] : "")
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
