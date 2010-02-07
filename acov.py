
import os 
import copy
import re
from Cheetah.Template import Template

VERBOSE = 0 
SOURCE_CODE_EXTENSIONS = [".cpp", ".cc", ".c"]
HEADER_CODE_EXTENSIONS = [".h"]
GRAPH_CODE_EXTENSION   = ".gcda"

EXTENSIONS = copy.copy(SOURCE_CODE_EXTENSIONS)
EXTENSIONS.extend(HEADER_CODE_EXTENSIONS)
EXTENSIONS.extend([GRAPH_CODE_EXTENSION])

class SingleIndexer:
    def __init__(self, dir, ext):
        self._files = []
        self._dir   = dir
        self._ext   = ext
        if VERBOSE > 0: print("\nVoy a indexar el directorio " + dir + " con la extension " + ext)
        cmd = "find " + dir + " -name '*" + ext + "'"

        pipe = os.popen(cmd)
        for file in pipe.readlines():
            file = file.strip()
            self._files.append(file)
            if VERBOSE > 1: print(file)
        pipe.close()
        if VERBOSE > 1: print("Tengo " + str(len(self._files)) + " archivos")

    def files(self):
        return self._files

    def dir(self):
        return self._dir

    def extension(self):
        return self._ext

    def have_file(self, filename_relative_to_base):
        supposed_filename = os.path.join(self._dir, filename_relative_to_base)
        if VERBOSE > 2: print("Me preguntan si tengo el archivo " + supposed_filename)
        return supposed_filename in self._files


class Indexer:
    def __init__(self, new_dir, old_dir, extension):
        self.new_indexer = SingleIndexer(new_dir, extension)
        if old_dir: 
            self.old_indexer = SingleIndexer(old_dir, extension)
        else:
            self.old_indexer = None

    def files(self):
        return self.new_indexer.files()

    def dir(self):
        return self.new_indexer.dir()

    def old_dir(self):
        return self.old_indexer.dir()

    def extension(self):
        return self.new_indexer.extension()
    
    def have_file(self, filename_relative_to_base):
        return self.new_indexer.have_file(filename_relative_to_base)

    def has_old_dir(self):
        return self.old_indexer != None


class ProjectTree:
    def __init__(self):
        self.indexers = {}
        self.reports = {}

    def add(self, new_dir, old_dir = None):
        if VERBOSE > 0: print("\nConsidero el directorio " + new_dir + " y busco el codigo fuente")
        self.indexers[new_dir] = {}
        for extension in EXTENSIONS:
            self.indexers[new_dir][extension] = Indexer(new_dir, old_dir, extension)

    def have_file(self, filename_relative_to_any_base):
        for dir in self.indexers:
            for extension in self.indexers[dir]:
                indexer = self.indexers[dir][extension]
                if indexer.have_file(filename_relative_to_any_base):
                    return True
        return False                

    def create_reports(self):
        if VERBOSE > 0: print("\nVoy a hacer una lista de todos los archivos que tengo indexados")
        for dir in self.indexers:
            for extension in EXTENSIONS:
                if extension == GRAPH_CODE_EXTENSION: continue
                indexer = self.indexers[dir][extension]
                for file in indexer.files():
                    if VERBOSE > 1: print("  Archivo: " + file)
                    if indexer.has_old_dir():
                        old_file = file.replace(indexer.dir(), "")
                        if old_file[0] == '/':
                            old_file = old_file[1:]
                        old_file = os.path.join(indexer.old_dir(), old_file)
                        if VERBOSE > 1: print("    El archivo viejo deberia ser " + old_file)
                        if os.path.exists(old_file): 
                            self.reports[file] = Report(file, old_file)
                        else:
                            self.reports[file] = Report(file)
                    else:
                        self.reports[file] = Report(file)

    def do_gcov(self):
        self.create_reports()
        if VERBOSE > 0: print("\nVoy a empezar a hacer gcov")
        for dir in self.indexers:
            self.do_gcov_over_directory(dir)
        if VERBOSE > 0: print("\nVoy a generar los informes")
        for file in self.reports:
            self.reports[file].generate_report()
        if VERBOSE > 0: print("\nVoy a generar el indice")

    def do_gcov_over_directory(self, dir):
        if VERBOSE > 0: print("  Voy a hacer gcov sobre el directorio " + dir)
        for extension in SOURCE_CODE_EXTENSIONS:
            indexer = self.indexers[dir][extension]
            self.do_gcov_over_indexer(indexer)

    def do_gcov_over_indexer(self, indexer):
        if VERBOSE > 0: print("    Voy a hacer gcov sobre la extension "+ indexer.extension())
        for filename in indexer.files():
            self.do_gcov_over_file(filename, indexer)

    def do_gcov_over_file(self, filename, indexer):
        if VERBOSE > 0: print("      Voy a hacer gcov al archivo " + filename)
        graph_filename = filename.replace(indexer.extension(), "") + GRAPH_CODE_EXTENSION
        if VERBOSE > 2: print("        Busco el archivo del grafo " + graph_filename)
        graph_indexer = self.indexers[indexer.dir()][GRAPH_CODE_EXTENSION]
        if graph_indexer.have_file(graph_filename):
             if VERBOSE > 1: print("        Tengo el archivo del grafo")
             self.analyze_gcov_over_file(filename, indexer)
        else:
             if VERBOSE > 1: print("        NO tengo el archivo del grafo")
             
    def analyze_gcov_over_file(self, filename, indexer):
        regexp_to_locate_directory_where_filename_lives = re.compile("^(.*)\/[^\/]*$")
        regexp_to_locate_filename_generated_by_gcov = re.compile("^(.*):creating '(.*)'$")
        matches = regexp_to_locate_directory_where_filename_lives.match(filename)
        directory_where_filename_lives = matches.group(1)
        directory_where_graph_lives = directory_where_filename_lives # normalmente
        if VERBOSE > 0: print("        Directorio " + directory_where_filename_lives)
        cmd = "cd " + directory_where_filename_lives + " && gcov -o " + directory_where_graph_lives + " " + filename
        pipe = os.popen(cmd)
        for gcov_output_line in pipe.readlines():
            gcov_output_line = gcov_output_line.strip()
            if VERBOSE > 2: print(gcov_output_line)
            matches = regexp_to_locate_filename_generated_by_gcov.match(gcov_output_line)
            if matches:
                source_filename = matches.group(1)
                generated_filename = matches.group(2)
                if source_filename[0] != '/':
                    source_filename = os.path.join(directory_where_filename_lives, source_filename)
                source_filename = os.path.abspath(source_filename)
                if VERBOSE > 0: print("          gCov ha generado el archivo " + generated_filename + " que hace referencia al archivo " + source_filename)
                self.analyze_coverage(directory_where_filename_lives, generated_filename, source_filename, filename)
        pipe.close()

    def analyze_coverage(self, directory, gcov_file, source_file, component_file):
        gcov_file = os.path.join(directory, gcov_file)
        if VERBOSE > 0: print("Voy a analizar la cobertura de " + source_file + " en base a " + gcov_file)
        regexp_to_parse_gcov_lines = re.compile("^([^:]*):([^:]*):(.*)")
        file = open(gcov_file, 'r')
        for gcov_line in file.readlines():
            if VERBOSE > 1: print(gcov_line)
            matches = regexp_to_parse_gcov_lines.match(gcov_line)
            if matches:
                line_count = matches.group(1).strip()
                if line_count == '-':
                    continue
                else:
                    if line_count == '#####':
                        line_count = 0
                    else:
                        line_count = int(line_count)
                line_number = int(matches.group(2).strip())
                line_text = matches.group(3)
                if VERBOSE > 2: print(line_number, line_count)
                if line_number > 0: self.reports[source_file].add_coverage(line_number, line_count, component_file)
            else:
                print("ERROR AL PARSEAR GCOV")
        file.close()


class Report:
    def __init__(self, new_file, old_file = None):
        self._new_file  = new_file
        self._old_file  = old_file
        self._new_lines = []
        self._coverage  = {}
        self._components = []
        self.get_diffs()

    def has_old_file(self):
        return self._old_file != None

    def add_coverage(self, line, count, component):
        if not (line in self._coverage):
            self._coverage[line] = 0
        self._coverage[line] += count 
        if not (component in self._components):
            self._components.extend([component])

    def coverage(self):
        return self._coverage

    def get_diffs(self):
        if VERBOSE > 0: print("  Voy a obtener las diferencias entre las versiones")
        if not self.has_old_file():
            if VERBOSE > 1: print("    No tengo archivo viejo, todo es nuevo")
        else:
            if VERBOSE > 1: print("    Tengo archivo viejo, saco las diferencias")
            temp_file = "/tmp/acov.tmpy"
            cmd = "cat " + self._old_file + " | sed -e 's/\\r//g' > " + temp_file + ".old"
            os.system(cmd)
            cmd = "cat " + self._new_file + " | sed -e 's/\\r//g' > " + temp_file + ".new"
            os.system(cmd)
            cmd = "diff " + temp_file + ".old " + temp_file + ".new"
            regexp_to_locate_diff_ranges = re.compile("^[0-9,]+([ac])([0-9,]*)")
            pipe = os.popen(cmd)
            for diff_output_line in pipe.readlines():
                if VERBOSE > 1: print diff_output_line
                matches = regexp_to_locate_diff_ranges.match(diff_output_line)
                if matches:
                    rango = matches.group(2)
                    rango = rango.split(",")
                    if len(rango) == 2:
                        inicio = int(rango[0])
                        fin = int(rango[1])
                        rango = range(inicio, fin + 1)
                    else:
                        rango = [int(rango[0])]
                    if VERBOSE > 1: print("diff << " + str(rango))
                    self._new_lines.extend(rango)
            pipe.close()

    def generate_report(self):
        if VERBOSE > 0: print("Generando informe del archivo " + self._new_file)
        report = """
<html>
  <head>
    <style type='text/css'>
      body 
      {
        font-size:11px;
        font-family:verdana
      }
      pre 
      {
        font-size:10px
      }

      .uncovered 
      {
        color:#f00;
      }
      .covered 
      {
        color:#000;
      }

      .uncovered_new 
      {
        background-color: #FF6230;
        color:#800;
        font-weight:bold;
      }
      .covered_new
      {
        background-color: #CAD7FE;
      }
      
      .noexec
      {
        color:#aaa;
      }
      table 
      {
        border-width:0;
        border-spacing:0
      }
      td 
      {
        border-width:0;
        border-bottom:1px solid #eed;
      }
      .linenum 
      {
        background-color: #EFE383;
        text-align:right;
        padding-right:1em;
      }
      h1 
      {
        border-bottom:1px solid #ccc
      }
      h2 
      {
        border-bottom:1px solid #ccc
      }
    </style>
  </head>
  <body>
    <h1> $filename </h1>
#if $old_filename
    <h2> (Derived from $old_filename) </h2>
#else
    <h2> (This file is new) </h2>
#end if
<div> 
  Components:
  <ul>
#for $component in $components
    <li> $component </li>
#end for
  </ul>
</div>
<h3> Legend </h3>

<table>
  <tbody>
#if $old_filename
    <tr>
      <td><pre>Old code</pre></td>
      <td><pre>New code</pre></td>
    </tr>
#end if
    <tr>
#if $old_filename
      <td colspan="2" class="noexec"> <pre>non-executable </pre></td>
#else
      <td class="noexec"> <pre>non-executable </pre></td>
#end if
    </tr>
    <tr>
#if $old_filename    
      <td class="covered"><pre>Covered</pre></td>
#end if
      <td class="covered_new"><pre>Covered</pre></td>
    </tr>
    <tr>
#if $old_filename
      <td class="uncovered"><pre>Uncovered</pre></td>
#end if
      <td class="uncovered_new"><pre>Uncovered</pre></td>
    </tr>
  </tbody>
</table>

<h3> Code </h3>

    <table>
      <tbody>
#set $line_number = 0
#for $line in $file_contents
#set $line_number = $line_number + 1

#if $line_number in $coverage
#if $coverage[$line_number] == 0
#set $tr_class = "uncovered"
#else
#set $tr_class = "covered"
#end if
#if ($line_number in $new_lines) or (not $old_filename)
#set $tr_class = $tr_class + "_new"
#end if
#else
#set $tr_class = "noexec"
#end if
        <tr class="$tr_class">
          <td class="linenum">
#if $line_number in $new_lines
            <pre>$line_number*</pre>
#else
            <pre>$line_number </pre>
#end if
          </td>
          <td>
#if $line_number in $coverage
            <pre>$coverage[$line_number]</pre>
#end if
          </td>
          <td class="$tr_class">
            <pre>$line.rstrip(" \\n").replace("<", "&lt;").replace(">", "&gt;")</pre>
          </td>
        </tr>
#end for
      </tbody>
    </table>
  </body>
</html>
"""
        template = Template(report)
        template.filename = self._new_file
        template.old_filename = self._old_file
        file = open(self._new_file, 'r')
        template.file_contents = file.readlines()
        template.coverage = self._coverage
        template.new_lines = self._new_lines
        template.components = self._components
        file.close()
        output = open(os.path.join("html",  self._new_file.replace("/", "_") + ".html"), 'w')
        output.write(str(template))
        output.close()












