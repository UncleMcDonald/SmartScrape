import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { Plus, Trash2, FileDown, FileJson, FileSpreadsheet, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState, type ChangeEvent, type KeyboardEvent } from "react";

// Add interface definitions for API response
interface ProductData {
  name: string;
  price: string;
  description: string;
  image_url?: string;
  "Main Image URL"?: string;
  Main_Image_URL?: string;
}

interface ResultItem {
  data: ProductData[];
  status: string;
  url: string;
  error?: string;
  reason?: string;
}

interface ApiResponse {
  success: boolean;
  data: {
    results: ResultItem[];
    metadata: {
      batch_id: string;
      processing_time_seconds: number;
      timestamp_utc: string;
    };
    failed: number;
    successful: number;
    total: number;
  };
}

interface ErrorInfo {
  url: string;
  message: string;
  reason?: string;
}

export default function AIScraperUI() {
  const [instruction, setInstruction] = useState<string>("");
  const [urls, setUrls] = useState<string[]>([""]);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [urlErrors, setUrlErrors] = useState<ErrorInfo[]>([]);
  const [failedUrls, setFailedUrls] = useState<Record<string, ErrorInfo>>({});
  const [rawApiData, setRawApiData] = useState<ProductData[]>([]);
  const [tableColumns, setTableColumns] = useState<string[]>(["Name", "Price", "Description"]);
  
  // Base64 encoded simple placeholder image
  const placeholderImageBase64 = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxMiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iIGZpbGw9IiM5OTk5OTkiPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==";
  
  // Define column mappings at component level so it's accessible in the render function
  const preferredOrder: Record<string, string> = {
    "Main Image URL": "Image",
    "image_url": "Image",
    "Main_Image_URL": "Image",
    "name": "Name", 
    "price": "Price",
    "description": "Description"
  };
  
  // Image related field names
  const imageFieldNames = ["Main Image URL", "image_url", "Main_Image_URL"];
  
  const [results, setResults] = useState<Record<string, any>[]>([]);

  const handleUrlChange = (i: number, v: string) => setUrls(urls => urls.map((x, idx) => (idx === i ? v : x)));
  const addUrlRow = () => setUrls(urls => [...urls, ""]);
  const removeUrlRow = (i: number) => setUrls(urls => (urls.length === 1 ? urls : urls.filter((_, idx) => idx !== i)));
  const handleKey = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && i === urls.length - 1) {
      e.preventDefault();
      addUrlRow();
    }
  };

  async function handleScrape() {
    const active = urls.map(x => x.trim()).filter(Boolean);
    if (!active.length) return;
    
    setIsRunning(true);
    setProgress(0);
    setResults([]);
    setError(null);
    setUrlErrors([]);
    setFailedUrls({});
    
    // Start progress simulation immediately
    let progressInterval: NodeJS.Timeout;
    let estimatedTimePerUrl = 2000; // Estimated ms per URL
    let totalEstimatedTime = active.length * estimatedTimePerUrl;
    let startTime = Date.now();
    
    const updateProgress = () => {
      const elapsedTime = Date.now() - startTime;
      const calculatedProgress = Math.min((elapsedTime / totalEstimatedTime) * 85, 85); // Cap at 85% until actual completion
      setProgress(calculatedProgress);
    };
    
    // Start progress updates every 100ms
    progressInterval = setInterval(updateProgress, 100);
    
    try {
      const response = await fetch('http://localhost:5000/api/batch-process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          urls: active,
          prompt: instruction || "Extract product name, price, description and image URL from these product pages, format as JSON",
          options: {
            parallel: 3
          }
        })
      });
      
      // As soon as we get a response, move progress to 90%
      setProgress(90);
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json() as ApiResponse;
      
      // After getting data, move to 95%
      setProgress(95);
      
      if (data.success) {
        try {
          // Collect errors for data items with error fields
          const errors: ErrorInfo[] = data.data.results
            .flatMap((result: ResultItem) => 
              result.data
                .filter((item: any) => item.error)
                .map((item: any) => ({
                  url: result.url,
                  message: item.error,
                  reason: item.reason
                }))
            );
          
          // Create lookup object for failed URLs
          const failedUrlsMap: Record<string, ErrorInfo> = {};
          errors.forEach(err => {
            failedUrlsMap[err.url] = err;
          });
          
          setFailedUrls(failedUrlsMap);
          
          if (errors.length > 0) {
            setUrlErrors(errors);
            if (errors.length === active.length) {
              setError(`All ${errors.length} URL(s) failed to process`);
            } else {
              setError(`${errors.length} out of ${active.length} URL(s) failed to process`);
            }
          }
          
          // Store the raw data for export - only from successful extractions
          const allProductData = data.data.results
            .filter((result: ResultItem) => result.status === "success")
            .flatMap((result: ResultItem) => result.data)
            .filter((item: any) => !item.error);
          
          setRawApiData(allProductData);
          
          // Only continue with successful results
          if (allProductData.length === 0) {
            if (errors.length === 0) {
              setError("No product data successfully extracted");
            }
            return;
          }
          
          // Extract all unique keys from response data for table columns
          const allKeys = new Set<string>();
          allProductData.forEach(item => {
            Object.keys(item).forEach(key => allKeys.add(key));
          });
          
          // Check if any image fields exist in the data
          const hasImageField = Array.from(allKeys).some(key => 
            imageFieldNames.includes(key) || key.toLowerCase().includes('image')
          );
          
          // Sort keys to put important ones first and explicitly exclude error fields
          const sortedKeys = Array.from(allKeys)
            .filter(key => !['error', 'reason'].includes(key.toLowerCase()))
            .sort((a, b) => {
              // If both keys have preferred mappings
              if (preferredOrder[a] && preferredOrder[b]) {
                // Sort by the order of the values in preferredOrder
                const aIndex = Object.values(preferredOrder).indexOf(preferredOrder[a]);
                const bIndex = Object.values(preferredOrder).indexOf(preferredOrder[b]);
                return aIndex - bIndex;
              }
              // If only a has a preferred mapping
              if (preferredOrder[a]) return -1;
              // If only b has a preferred mapping
              if (preferredOrder[b]) return 1;
              // Otherwise sort alphabetically
              return a.localeCompare(b);
            });
          
          // Map to friendly names where available
          let displayColumns = sortedKeys.map(key => preferredOrder[key] || key);
          
          // Remove duplicates (e.g. multiple image fields mapping to same "Image" column)
          displayColumns = Array.from(new Set(displayColumns));
          
          // Update table columns
          setTableColumns(displayColumns);
          
          // Process successful results for display
          const processedResults = data.data.results
            .filter((result: ResultItem) => result.status === "success")
            .flatMap((result: ResultItem) => 
              result.data
                .filter((item: ProductData) => {
                  // Exclude any items that have error or reason fields
                  const itemAsAny = item as any;
                  return !itemAsAny.error && !itemAsAny.reason;
                })
                .map((item: ProductData) => {
                  // Create a base result object with image field only if needed
                  const resultItem: Record<string, any> = {
                    name: item.name || 'Unknown Name',
                    price: item.price || 'N/A',
                    description: item.description || 'No description available',
                  };
                  
                  // Only add image property if we have image fields in the data
                  if (hasImageField) {
                    resultItem.image = item.Main_Image_URL || item["Main Image URL"] || item.image_url || placeholderImageBase64;
                  }
                  
                  // Add all additional fields from the original data, excluding error-related fields
                  for (const key of sortedKeys) {
                    if (!['name', 'price', 'description', 'error', 'reason'].includes(key.toLowerCase()) && 
                        !key.toLowerCase().includes('image')) {
                      resultItem[key] = item[key as keyof ProductData] || '';
                    }
                  }
                  
                  return resultItem;
                })
            );
          
          setResults(processedResults);
        } catch (err: any) {
          console.error("Error processing API response:", err);
          setError(`Error processing API response: ${err.message || "Unknown error"}`);
        }
      } else {
        console.error("API returned an error:", data);
        setError(`API request failed: ${data.data?.failed || 0} URL(s) failed to process`);
      }
    } catch (error: any) {
      console.error("Error fetching data:", error);
      setError(error.message || "An error occurred. Please try again later");
    } finally {
      // Clear the interval and set progress to 100%
      if (progressInterval) clearInterval(progressInterval);
      setProgress(100);
      setIsRunning(false);
    }
  }

  const handleExportCSV = () => {
    if (!rawApiData.length) return;
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    // Get all unique keys from all data objects
    const allKeys = new Set<string>();
    rawApiData.forEach(item => {
      Object.keys(item).forEach(key => allKeys.add(key));
    });
    
    const headers = Array.from(allKeys);
    
    // Create rows with all fields
    const rows = [
      headers,
      ...rawApiData.map(item => 
        headers.map(key => {
          // Safely access the property which might not exist on all items
          return (item as any)[key] !== undefined ? (item as any)[key] : '';
        })
      )
    ];
    
    const csv = rows.map(r => r.map(v => {
      // Handle commas, quotes, and newlines in CSV
      const value = String(v).replace(/"/g, '""');
      return `"${value}"`;
    }).join(",")).join("\n");
    
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scraped_results_${timestamp}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  
  const handleExportJSON = () => {
    if (!rawApiData.length) return;
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const jsonStr = JSON.stringify(rawApiData, null, 2);
    
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scraped_results_${timestamp}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  
  const handleExportExcel = async () => {
    if (!rawApiData.length) return;
    
    try {
      // Dynamically import the xlsx library
      const XLSX = await import('xlsx').then(mod => mod.default);
      
      // Get all unique keys from all data objects
      const allKeys = new Set<string>();
      rawApiData.forEach(item => {
        Object.keys(item).forEach(key => allKeys.add(key));
      });
      
      const headers = Array.from(allKeys);
      
      // Prepare worksheet data
      const wsData = [
        headers,
        ...rawApiData.map(item => 
          headers.map(key => (item as any)[key] !== undefined ? (item as any)[key] : '')
        )
      ];
      
      // Create worksheet
      const ws = XLSX.utils.aoa_to_sheet(wsData);
      
      // Create workbook
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Scraped Data");
      
      // Generate timestamp for filename
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      
      // Export to Excel
      XLSX.writeFile(wb, `scraped_results_${timestamp}.xlsx`);
    } catch (error) {
      console.error("Failed to export Excel file:", error);
      alert("Excel export failed. Please ensure the xlsx library is installed and try again.");
    }
  };

  // Replace the existing export UI with dropdown buttons
  const renderExportButtons = () => {
    return (
      <div className="flex space-x-2">
        <Button 
          size="sm" 
          variant="outline" 
          onClick={handleExportCSV} 
          className="flex items-center gap-1 bg-blue-50 hover:bg-blue-100 text-blue-700"
          disabled={!results.length}
        >
          <FileDown className="w-4 h-4" />
          CSV
        </Button>
        <Button 
          size="sm" 
          variant="outline" 
          onClick={handleExportJSON} 
          className="flex items-center gap-1 bg-green-50 hover:bg-green-100 text-green-700"
          disabled={!results.length}
        >
          <FileJson className="w-4 h-4" />
          JSON
        </Button>
        <Button 
          size="sm" 
          variant="outline" 
          onClick={handleExportExcel} 
          className="flex items-center gap-1 bg-purple-50 hover:bg-purple-100 text-purple-700"
          disabled={!results.length}
        >
          <FileSpreadsheet className="w-4 h-4" />
          Excel
        </Button>
      </div>
    );
  };

  // Render error messages
  // const renderErrors = () => {
  //   if (!urlErrors.length) return null;
    
  //   return (
  //     <div className="mt-4 border border-red-200 rounded-lg bg-red-50 p-3">
  //       <div className="flex items-center gap-2 text-sm text-red-600 font-medium mb-2">
  //         <AlertCircle className="h-4 w-4" />
  //         Failed URLs
  //       </div>
  //       <div className="max-h-40 overflow-y-auto">
  //         {urlErrors.map((err, i) => (
  //           <div key={i} className="text-xs mb-2 pb-2 border-b border-red-100 last:border-0">
  //             <div className="font-semibold text-red-700 truncate" title={err.url}>{err.url}</div>
  //             <div className="text-red-600">{err.message || "Failed to extract data"}</div>
  //             {err.reason && <div className="text-red-500 mt-1">{err.reason}</div>}
  //           </div>
  //         ))}
  //       </div>
  //     </div>
  //   );
  // };

  // Replace the URL input rendering with error indicators
  const renderUrlInput = (u: string, i: number) => {
    const isUrlFailed = failedUrls[u] !== undefined;
    const errorInfo = isUrlFailed ? failedUrls[u] : null;
    
    return (
      <motion.div key={i} layout className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Input 
            value={u} 
            onChange={(e: ChangeEvent<HTMLInputElement>) => handleUrlChange(i, e.target.value)} 
            onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => handleKey(i, e)} 
            placeholder={`https://example.com/product/${i + 1}`} 
            className={`flex-1 bg-white/70 border-slate-300 focus:ring-indigo-500 ${isUrlFailed ? 'border-red-400' : ''}`}
          />
          {urls.length > 1 && (
            <Button 
              size="icon" 
              variant="ghost" 
              onClick={() => removeUrlRow(i)} 
              className="hover:bg-red-50"
            >
              <Trash2 className="w-4 h-4 text-red-600" />
            </Button>
          )}
          {isUrlFailed && (
            <div className="flex items-center justify-center bg-red-100 rounded-full p-1 w-6 h-6">
              <AlertCircle className="w-4 h-4 text-red-600" />
            </div>
          )}
        </div>
        {isUrlFailed && errorInfo && (
          <div className="text-xs text-red-600 ml-1 mb-1">
            {errorInfo.message}
          </div>
        )}
      </motion.div>
    );
  };

  const container = "min-h-dvh w-full bg-gradient-to-br from-[#f8fafc] via-[#eef2ff] to-[#e0e7ff] text-slate-800 px-4 py-6";
  const grid = "w-full h-full flex flex-col gap-6 md:grid md:grid-cols-2 md:gap-8";
  const cardShared = "h-full w-full backdrop-blur bg-white/80 border border-slate-200 shadow-xl rounded-2xl flex flex-col";

  return (
    <div className={container}>
      <div className="mx-auto max-w-[90rem] h-full">
        <div className={grid} style={{ height: "100%" }}>
          <motion.div className="flex" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card className={cardShared}>
              <CardHeader>
                <CardTitle className="text-3xl font-semibold tracking-tight text-indigo-700">AI Scraper Portal</CardTitle>
                <CardDescription className="text-sm">Provide an instruction and product URLs.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-6 flex-grow overflow-y-auto">
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Instruction</label>
                  <Textarea 
                    value={instruction} 
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setInstruction(e.target.value)} 
                    placeholder="e.g. Extract Product Name, Price, Description, Image URL" 
                    className="resize-none min-h-[100px] bg-white/70 border-slate-300 focus:ring-indigo-500" 
                  />
                </div>
                <div className="grid gap-2">
                  <label className="text-sm font-medium flex items-center gap-2">URLs
                    <Button type="button" size="icon" variant="secondary" onClick={addUrlRow} className="bg-indigo-50 hover:bg-indigo-100"><Plus className="w-4 h-4 text-indigo-600" /></Button>
                  </label>
                  <div className="grid gap-2 max-h-60 overflow-y-auto pr-2">
                    {urls.map((u, i) => renderUrlInput(u, i))}
                  </div>
                </div>
                <div className="flex items-center gap-4 sticky bottom-0 bg-white/80 pt-4 pb-2">
                  <Button onClick={handleScrape} disabled={isRunning || urls.every(x => !x.trim())} className="bg-indigo-600 hover:bg-indigo-700 text-white">{isRunning ? "Scraping..." : "Scrape"}</Button>
                  {isRunning && <Progress value={progress} className="w-full bg-indigo-100" />}
                  {error && <div className="text-red-600 text-sm ml-4">{error}</div>}
                </div>
              </CardContent>
            </Card>
          </motion.div>
          <AnimatePresence mode="wait">
            {results.length > 0 && (
              <motion.div key="table" initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 50 }} transition={{ duration: 0.6 }} className="flex">
                <Card className={cardShared}>
                  <CardHeader className="flex flex-row items-center justify-between gap-2">
                    <div>
                      <CardTitle className="text-2xl text-indigo-700">Preview</CardTitle>
                      <CardDescription>{results.length} product(s) scraped</CardDescription>
                    </div>
                    {renderExportButtons()}
                  </CardHeader>
                  <CardContent className="overflow-y-auto flex-grow">
                    <Table className="text-sm">
                      <TableHeader>
                        <TableRow>
                          {tableColumns.map((column, i) => (
                            <TableHead 
                              key={i} 
                              className={column === 'Image' ? 'w-[90px]' : 
                                         column === 'Name' ? 'w-[250px]' : 
                                         column === 'Price' ? 'w-[80px]' : ''}
                            >
                              {column}
                            </TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {results.map((item, i) => (
                          <TableRow key={i} className="hover:bg-indigo-50/40">
                            {tableColumns.map((column, j) => {
                              // Handle image column specially
                              if (column === 'Image') {
                                return (
                                  <TableCell key={j} className="p-2">
                                    {item.image ? (
                                      <img 
                                        src={item.image} 
                                        alt={item.name} 
                                        className="w-16 h-16 rounded-lg object-cover"
                                        onError={(e) => {
                                          const target = e.target as HTMLImageElement;
                                          target.src = placeholderImageBase64;
                                        }} 
                                      />
                                    ) : null}
                                  </TableCell>
                                );
                              }
                              
                              // For other columns, display text content
                              const key = Object.keys(preferredOrder).find(
                                k => preferredOrder[k] === column
                              ) || column;
                              
                              const value = item[key.toLowerCase()] || item[key] || '';
                              
                              return (
                                <TableCell 
                                  key={j}
                                  className={`p-2 ${column === 'Name' ? 'font-medium break-words whitespace-normal max-w-[250px]' : 
                                                     column === 'Description' ? 'max-w-sm line-clamp-2' : ''}`}
                                  title={typeof value === 'string' ? value : JSON.stringify(value)}
                                >
                                  {typeof value === 'string' ? value : JSON.stringify(value)}
                                </TableCell>
                              );
                            })}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}