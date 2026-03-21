import React, { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, Plus, FileText, Upload, Trash2, Download, CalendarDays } from "lucide-react";
import { motion } from "framer-motion";

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleString();
}

async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function NotesAndFilesApp() {
  const [items, setItems] = useState(() => {
    const saved = localStorage.getItem("notes-files-app-items");
    return saved ? JSON.parse(saved) : [];
  });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  const [noteOpen, setNoteOpen] = useState(false);
  const [fileOpen, setFileOpen] = useState(false);

  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");

  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);

  useEffect(() => {
    localStorage.setItem("notes-files-app-items", JSON.stringify(items));
  }, [items]);

  const filteredItems = useMemo(() => {
    return items
      .filter((item) => {
        if (filter === "all") return true;
        return item.type === filter;
      })
      .filter((item) => {
        const q = search.toLowerCase().trim();
        if (!q) return true;
        if (item.type === "note") {
          return (
            item.title.toLowerCase().includes(q) ||
            item.content.toLowerCase().includes(q)
          );
        }
        return (
          item.name.toLowerCase().includes(q) ||
          item.mimeType.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }, [items, search, filter]);

  const stats = useMemo(() => {
    const notes = items.filter((item) => item.type === "note").length;
    const files = items.filter((item) => item.type === "file").length;
    return { notes, files, total: items.length };
  }, [items]);

  const handleCreateNote = () => {
    if (!noteTitle.trim() && !noteContent.trim()) return;

    const newNote = {
      id: crypto.randomUUID(),
      type: "note",
      title: noteTitle.trim() || "Untitled note",
      content: noteContent.trim(),
      createdAt: new Date().toISOString(),
    };

    setItems((prev) => [newNote, ...prev]);
    setNoteTitle("");
    setNoteContent("");
    setNoteOpen(false);
  };

  const handleFileSelection = async (event) => {
    const files = Array.from(event.target.files || []);
    const mapped = await Promise.all(
      files.map(async (file) => ({
        id: crypto.randomUUID(),
        type: "file",
        name: file.name,
        size: file.size,
        mimeType: file.type || "unknown",
        createdAt: new Date().toISOString(),
        dataUrl: await fileToDataUrl(file),
      }))
    );
    setSelectedFiles(mapped);
  };

  const handleSaveFiles = () => {
    if (!selectedFiles.length) return;
    setItems((prev) => [...selectedFiles, ...prev]);
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setFileOpen(false);
  };

  const handleDelete = (id) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 rounded-3xl bg-white p-6 shadow-sm"
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Notes + Files</h1>
              <p className="mt-1 text-sm text-slate-500">
                A simple starter app for creating notes and storing uploaded files in one place.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Dialog open={noteOpen} onOpenChange={setNoteOpen}>
                <DialogTrigger asChild>
                  <Button className="rounded-2xl">
                    <Plus className="mr-2 h-4 w-4" />
                    New Note
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-xl rounded-3xl">
                  <DialogHeader>
                    <DialogTitle>Create a note</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <Input
                      placeholder="Note title"
                      value={noteTitle}
                      onChange={(e) => setNoteTitle(e.target.value)}
                      className="rounded-2xl"
                    />
                    <Textarea
                      placeholder="Write your note here..."
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      className="min-h-[220px] rounded-2xl"
                    />
                    <div className="flex justify-end">
                      <Button onClick={handleCreateNote} className="rounded-2xl">Save Note</Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              <Dialog open={fileOpen} onOpenChange={setFileOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="rounded-2xl">
                    <Upload className="mr-2 h-4 w-4" />
                    New File Upload
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-xl rounded-3xl">
                  <DialogHeader>
                    <DialogTitle>Upload files</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <label className="block rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
                      <Upload className="mx-auto mb-3 h-8 w-8 text-slate-500" />
                      <p className="text-sm font-medium">Choose one or more files</p>
                      <p className="mt-1 text-xs text-slate-500">Files are stored locally in this browser for now.</p>
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="mt-4 block w-full text-sm"
                        onChange={handleFileSelection}
                      />
                    </label>

                    {!!selectedFiles.length && (
                      <div className="space-y-2 rounded-2xl border p-3">
                        {selectedFiles.map((file) => (
                          <div key={file.id} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{file.name}</p>
                              <p className="text-xs text-slate-500">{formatBytes(file.size)} • {file.mimeType}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex justify-end">
                      <Button onClick={handleSaveFiles} className="rounded-2xl">Save Files</Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Card className="rounded-3xl shadow-sm">
              <CardContent className="p-5">
                <p className="text-sm text-slate-500">Notes</p>
                <p className="mt-2 text-2xl font-semibold">{stats.notes}</p>
              </CardContent>
            </Card>
            <Card className="rounded-3xl shadow-sm">
              <CardContent className="p-5">
                <p className="text-sm text-slate-500">Files</p>
                <p className="mt-2 text-2xl font-semibold">{stats.files}</p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <Card className="rounded-3xl bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Browse</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search notes or files"
                  className="rounded-2xl pl-9"
                />
              </div>

              <Tabs value={filter} onValueChange={setFilter}>
                <TabsList className="grid w-full grid-cols-3 rounded-2xl">
                  <TabsTrigger value="all" className="rounded-2xl">All</TabsTrigger>
                  <TabsTrigger value="note" className="rounded-2xl">Notes</TabsTrigger>
                  <TabsTrigger value="file" className="rounded-2xl">Files</TabsTrigger>
                </TabsList>
              </Tabs>

              <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                This version is frontend only. It uses local browser storage right now, which makes it easy to later swap in a backend and user accounts.
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-3xl bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Library</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[560px] pr-4">
                {filteredItems.length === 0 ? (
                  <div className="flex min-h-[400px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 text-center">
                    <FileText className="mb-4 h-10 w-10 text-slate-400" />
                    <p className="text-base font-medium">Nothing here yet</p>
                    <p className="mt-1 max-w-sm text-sm text-slate-500">
                      Create your first note or upload your first file to get started.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {filteredItems.map((item, index) => (
                      <motion.div
                        key={item.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.03 }}
                      >
                        <Card className="rounded-3xl border-slate-200 shadow-sm">
                          <CardContent className="p-5">
                            <div className="flex items-start justify-between gap-4">
                              <div className="min-w-0 flex-1">
                                <div className="mb-3 flex flex-wrap items-center gap-2">
                                  <Badge variant="secondary" className="rounded-xl">
                                    {item.type === "note" ? "Note" : "File"}
                                  </Badge>
                                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                                    <CalendarDays className="h-3.5 w-3.5" />
                                    {formatDate(item.createdAt)}
                                  </span>
                                </div>

                                {item.type === "note" ? (
                                  <>
                                    <h3 className="text-lg font-semibold">{item.title}</h3>
                                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">
                                      {item.content || "No content"}
                                    </p>
                                  </>
                                ) : (
                                  <>
                                    <h3 className="truncate text-lg font-semibold">{item.name}</h3>
                                    <p className="mt-2 text-sm text-slate-600">
                                      {item.mimeType} • {formatBytes(item.size)}
                                    </p>
                                    <div className="mt-4">
                                      <a
                                        href={item.dataUrl}
                                        download={item.name}
                                        className="inline-flex items-center rounded-2xl border px-3 py-2 text-sm font-medium hover:bg-slate-50"
                                      >
                                        <Download className="mr-2 h-4 w-4" />
                                        Download file
                                      </a>
                                    </div>
                                  </>
                                )}
                              </div>

                              <Button
                                variant="ghost"
                                size="icon"
                                className="rounded-2xl"
                                onClick={() => handleDelete(item.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
