# Third-party notices

The cowork-canvas plugin ships these libraries in `server/bin/`, or inlined into the panel. Each is
used unmodified. The licence named here is the one its project publishes; the full texts are in each
project's repository.

| Component | Used for | Licence | Project |
|---|---|---|---|
| ModelContextProtocol, ModelContextProtocol.Core, ModelContextProtocol.Extensions.Apps 2.4.0 | The MCP server and the MCP Apps metadata | Apache-2.0 | https://github.com/modelcontextprotocol/csharp-sdk |
| @modelcontextprotocol/ext-apps 2.0.4 (`app-with-deps.js`, inlined into the panel) | The panel's side of the MCP Apps protocol | MIT | https://github.com/modelcontextprotocol/ext-apps |
| PDFiumCore 157.0.8100 | .NET bindings for PDFium | Apache-2.0 | https://github.com/Dtronix/PDFiumCore |
| PDFium (native library, via bblanchon.PDFium) | Rendering PDF pages | BSD-3-Clause and Apache-2.0 | https://pdfium.googlesource.com/pdfium |
| SkiaSharp 4.157.0 and its native Skia library | Encoding images | MIT (SkiaSharp), BSD-3-Clause (Skia) | https://github.com/mono/SkiaSharp |
| Microsoft.Extensions.* 10.0.14 | Hosting, logging, dependency injection | MIT | https://github.com/dotnet/runtime |

The licence column was written from each project's public statement at the time of the first build
and is to be re-checked against the package contents before the plugin is distributed beyond test
seats.
