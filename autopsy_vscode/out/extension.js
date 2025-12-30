"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.outputChannel = void 0;
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const webviewPanel_1 = require("./webviewPanel");
// Create output channel for debugging
exports.outputChannel = vscode.window.createOutputChannel('Autopsy Viewer');
function activate(context) {
    exports.outputChannel.appendLine('Autopsy Viewer extension activated');
    console.log('Autopsy Viewer extension activated');
    // Register command to open the Autopsy viewer
    const openViewerCmd = vscode.commands.registerCommand('autopsy.openViewer', () => {
        exports.outputChannel.appendLine('Opening Autopsy Viewer...');
        exports.outputChannel.show(true); // Show output channel (preserveFocus=true)
        try {
            webviewPanel_1.AutopsyPanel.createOrShow(context.extensionUri, exports.outputChannel);
            exports.outputChannel.appendLine('Autopsy Viewer panel created successfully');
        }
        catch (error) {
            exports.outputChannel.appendLine(`Error creating panel: ${error}`);
            vscode.window.showErrorMessage(`Failed to open Autopsy Viewer: ${error}`);
        }
    });
    // Register command to show output logs
    const showLogsCmd = vscode.commands.registerCommand('autopsy.showLogs', () => {
        exports.outputChannel.show();
    });
    context.subscriptions.push(openViewerCmd);
    context.subscriptions.push(showLogsCmd);
    context.subscriptions.push(exports.outputChannel);
}
function deactivate() {
    exports.outputChannel.appendLine('Autopsy Viewer extension deactivated');
    console.log('Autopsy Viewer extension deactivated');
}
//# sourceMappingURL=extension.js.map