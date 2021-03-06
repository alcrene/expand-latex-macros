r"""
                     EXPAND_LATEX_MACROS

                Copyright © 2020 Alexandre René

                        based on the
                          DE-MACRO
                 package by Péter Gács (© 2005)



This is first and foremost a Python3 port of the de-macro package. It also calls the FLaP package to first flatten the directory.
The original docstring for the de-macro package follows below.

Usage:

    expand-latex-macros [.tex file] [output directory]

`.tex file` is your usual main file – the one you run `(pdf)latex` on.
The contents of `output directory` will be overwritten the the merged and expanded tex files.
Macros definitions should be in a file whose name ends with `-private.sty` and imported with `\usepackage`.

---
Original docstring

PURPOSE

This program can eliminate most private macros from a LaTeX file.
Applications:
  - your publisher has difficulty dealing with many private macros
  - you cooperate with colleagues who do not understand your macros
  - preprocessing before a system like latex2html, which is somewhat
    unpredictable with private macros.

USAGE

de-macro [--defs <defs-db>] <tex-file-1>[.tex] [<tex-file-2>[.tex] ...]

Simplest example:    de-macro testament

(As you see, the <> is used only in the notation of this documentation,
you should not type it.)

If <tex-file-i> contains a command \usepackage{<defs-file>-private}
then the file <defs-file>-private.sty will be read, and its macros will be
replaced  in <tex-file-i> with their definitions.
The result is in <tex-file-i>-clean.tex.

Only newcommand, renewcommand, newenvironment, and renewenvironment are
understood (it does not matter, whether you write new or renew).
These can be nested but do not be too clever, since I do not
guarantee the same expansion order as in TeX.

FILES

<tex-file-1>.db
<tex-file>-clean.tex
<defs-file>-private.sty

For speed, a macro database file called <defs-file>.db is created.
If such a file exists already then it is used.
If <defs-file>-private.sty is older than <tex-file-1>.db then it will not
be used.

It is possible to specify another database filename via --defs <defs-db>.
Then <defs-db>.db will be used.

For each <tex-file-i>, a file <tex-file-i>-clean.tex will be produced.
If <tex-file-i>-clean.tex is newer than <tex-file-i>.tex then it stays.

INPUT COMMAND

If a tex file contains a command \input{<tex-file-j>} or \input <tex-file-j>
then <tex-file-j>.tex is processed recursively, and <tex-file-j>-clean.tex
will be inserted into the final output.
For speed, if <tex-file-j>-clean.tex is newer than <tex-file-j>.tex
then <tex-file-j>.tex will not be reprocessed.

The dependency checking is not sophisticated, so if you rewrite some macros
then remove all *-clean.tex files!

"""

import sys, os, re, shelve
from warnings import warn
from pathlib import Path
import shutil

import click
import flap.ui

# Utilities

class No_detail:
    strerror = ""

no_detail = No_detail()

# class Error(Exception):
#     """Base class for exceptions in this module."""
#     pass

class ArgumentError(RuntimeError):
    pass

class ParsingError(ValueError):
    pass

class Empty_text_error(ValueError):
    """Exception raised for errors in the input.

    Attributes:
        data -- data that was found empty
        message
    """

    def __init__(self, data, message):
        self.data = data
        self.message = message

def die(error_message, exception):
    emsg = str(exception)
    if len(emsg) > 0:
        error_message += '\n' + emsg
    warn(error_message)
    sys.exit(1)

def getopt_map(one_letter_opts, long_optlist):
    "Turns long options into an option map, using getopt."
    import getopt
    optlist, args = getopt.getopt(sys.argv[1:],
                                  one_letter_opts, long_optlist)
    opt_map = {}
    for pair in optlist: opt_map[pair[0]] = pair[1] or 1
    return opt_map, args

def newer(file1, file2):

    if not os.path.isfile(file1):
        return False

    try:
        stat_return = os.lstat(file1)
    except OSError as e:
        die("lstat " + file1 + " failed:", e)
    time1 = stat_return.st_mtime

    try:
        stat_return = os.lstat(file2)
    except OSError as e:
        die("lstat " + file2 + " failed:", e)
    time2 = stat_return.st_mtime

    return time1 > time2

def cut_extension(filename, ext):
    """
    If filename has extension ext (including the possible dot),
    it will be cut off.
    """
    file = filename
    index = filename.rfind(ext)
    if 0 <= index and len(file)-len(ext) == index:
        file = file[:index]
    return file


class Stream:
    data = None
    pos = None
    item = None

    def legal(self):
        return 0 <= self.pos and self.pos < len(self.data)

    def uplegal(self):
        return self.pos < len(self.data)

    def __init__(self, data_v = None):
        self.data = data_v
        if self.data:
           self.pos = 0
           self.item = self.data[self.pos]

    def next(self):
        self.pos += 1
        if self.pos < len(self.data):
            self.item = self.data[self.pos]
            return self.item

    def reset(self):
        if self.data and 0 < len(self.data):
            self.pos = 0
            self.item = self.data[0]
            return self.item


# Basic classes

blank_re = re.compile(r"\s")
blanked_filename_re = re.compile(r"^\s+(\w*)\s+")
braced_filename_re = re.compile(r"^\s*{\s*(\w*)\s*}")
blank_or_rbrace_re = re.compile(r"[\s}]")
pos_digit_re = re.compile(r"[1-9]")

def isletter(c, isatletter=False):
    if "@" == c:
        return isatletter
    else:
        return c.isalpha()

class Token:
    r"""Type 0 means ordinary character, type 1 means escape sequence
    (without the \ ), type 2 means comment.
    """
    simple_ty = 0
    esc_symb_ty = 1
    esc_str_ty = 2
    comment_ty = 3

    type = simple_ty
    val = " "

    def __init__(self, type_v=simple_ty, val_v=" "):
        self.type = type_v
        self.val = val_v

    def show(self, isatletter=False):
        out = ""
        if simple_ty == self.type or comment_ty == self.type:
            out = self.val
        else:
            out = "\\" + self.val
        return out


# Constants

g_token = Token(0," ")  # generic token
simple_ty = g_token.simple_ty
comment_ty = g_token.comment_ty
esc_symb_ty = g_token.esc_symb_ty
esc_str_ty = g_token.esc_str_ty



def detokenize(text):
    """
    Input is a list of tokens.
    Output is a string.
    """
    out = ""
    if 0 == len(text):
        return
    pos = 0
    out += text[pos].show()
    pos += 1
    while pos < len(text):
        previtem = text[pos-1]
        item = text[pos]
        """Insert a separating space after an escape sequence if it is a
        string and is followed by a letter."""
        if (esc_str_ty == previtem.type
            and simple_ty == item.type and isletter(item.val[0], False)):
            out += " "
        out += item.show()
        pos += 1
    return out

def strip_comments(text):
    """
    Input is a list of tokens.
    Output is the same list except the comment tokens.
    """
    out = []
    for token in text:
        if not comment_ty == token.type:
            out.append(token)
    return out

class Group:
    """type 0 means a token, type 1 means contents of a group within {}
    """
    token_ty = 0
    group_ty = 1
    type = token_ty
    val = [] # Value is a token list.

    def __init__(self, type_v, val_v):
        self.type = type_v
        self.val = val_v

    def show(self):
        if token_ty == self.type:
            return self.val.show()
        else:
            return "{%s}" % detokenize(self.val)

# Constants

g_group = Group(0, [])
token_ty = g_group.token_ty
group_ty = g_group.group_ty


def tokenize(in_str):
    """Returns a list of tokens.
    """
    text = []
    isatletter=False
    cs = Char_stream(in_str)
    cs.reset()
    if not cs.legal():
        raise ValueError("No string to tokenize.")
    while cs.uplegal():
        if "%" == cs.item:
            comment = cs.scan_comment_token()
            text.append(Token(comment_ty, comment))
        elif "\\" != cs.item:
            text.append(Token(simple_ty, cs.item))
            cs.next()
        else:
            cs.next()
            name = cs.scan_escape_token(isatletter)
            if isletter(name[0], isatletter):
                token = Token(esc_str_ty, name)
            else:
                token = Token(esc_symb_ty, name)
            text.append(token)
            if "makeatletter" == name:
                isatletter=True
            elif "makeatother" == name:
                isatletter=False
    return text



class Command_def:
    name = "1"
    numargs = 0
    body= ""

    def __init__(self, name_v, numargs_v, body_v):
        self.name = name_v
        self.numargs = numargs_v
        self.body = body_v

    def show(self):
        out = "\\newcommand{\\%s}" % (self.name)
        if 0 < self.numargs:
            out += "[%d]" % self.numargs
        out += "{%s}" % detokenize(self.body)
        return out


class Env_def:
    name = "1"
    numargs = 0
    begin = ""
    end = ""

    def __init__(self, name_v, numargs_v, begin_v, end_v):
        self.name = name_v
        self.numargs = numargs_v
        self.begin = begin_v
        self.end = end_v

    def show(self):
        out = "\\newenvironment{%s}" % self.name
        if 0 < self.numargs:
            out += "[%d]" % self.numargs
        out += "{%s}" % detokenize(self.begin)
        out += "{%s}" % detokenize(self.end)
        return out


class Command_instance:
    name = "1"
    args = []

    def __init__(self, name_v, args_v):
        self.name = name_v
        self.args = args_v

    def show(self):
        out = "\\"+self.name
        for arg in self.args:
            out += "{%s}" % detokenize(arg)
        return out


class Env_instance:
    name = "1"
    args = []

    def __init__(self, name_v, args_v, body_v):
        self.name = name_v
        self.args = args_v
        self.body = body_v

    def show(self):
        out = "\\begin{%s}" % self.name
        for arg in self.args:
            out += "{%s}" % detokenize(arg)
        out += detokenize(self.body)
        out += "\\end{%s}" % self.name
        return out

class Char_stream(Stream):

    def scan_escape_token(self, isatletter=False):
        """
        Starts after the escape sign, assumes that it is scanning a symbol.
        Returns a token-string.
        """
        out = self.item # Continue only if this is a letter.
        item = self.next()
        if isletter(out, isatletter):
            while self.uplegal() and isletter(item, isatletter):
                out += item
                item = self.next()
        return out

    def scan_comment_token(self):
        """
        Starts at the comment sign %, assumes that it is scanning a comment.
        Returns the whole comment string,
        including the % and all empty space after it.
        """
        comment = ""
        while "\n" != self .item:
            comment += self.item
            self.next()
        while self.uplegal() and blank_re.match(self.item):
            comment += self.item
            self.next()
        return comment

    def scan_input_filename(self):
        r"""We just read an \input token.  The next group or word will be
        interpreted as a filename (possibly without .tex).
        Return the filename.
        """
        item = self.item
        while self.uplegal() and blank_re.match(self.item):
            item = self.next()
        if "{" == item:
            item = self.next()
        file = ""
        while self.uplegal() and not blank_or_rbrace_re.match(item):
            file += item
            item = self.next()
        self.next()
        return file

    def scan_package_filenames(self):
        r"""We just read a \usepackage token.  The next group will be
        interpreted as a list of filenames (without .sty) separated by commas.
        Return the list.
        """
        item = self.item
        while self.uplegal() and blank_re.match(item):
            item = self.next()
        file = ""
        if not "{" == item:
            raise ParsingError("\\usepackage not followed by brace.")
        item = self.next()
        while self.uplegal() and not blank_or_rbrace_re.match(item):
            file += item
            item = self.next()
        self.next()
        return file.split(",")


class Tex_stream(Stream):

    defs = ({}, {})
    defs_db = "x"
    defs_db_file = "x.db"
    debug = False

    def smart_tokenize(self, in_str, handle_inputs=False):
        r"""Returns a list of tokens.
        It may interpret and carry out all \input commands.
        """
        self.data = []
        text = self.data
        isatletter=False
        cs = Char_stream(in_str)
        cs.reset()
        if not cs.legal():
            raise ValueError("No string to tokenize.")
        while cs.uplegal():
            if "%" == cs.item:
                comment = cs.scan_comment_token()
                text.append(Token(comment_ty, comment))
            elif "\\" != cs.item:
                text.append(Token(simple_ty, cs.item))
                cs.next()
            else:
                cs.next()
                name = cs.scan_escape_token(isatletter)
                if "input" == name and handle_inputs:
                    file = cs.scan_input_filename()
                    to_add = self.process_if_newer(file)
                    text.extend(to_add)
                elif "usepackage" == name:
                    while cs.uplegal() and blank_re.match(cs.item):
                        cs.next()
                    if "[" == cs.item: # private packages have no options
                        text.extend([Token(esc_str_ty, "usepackage"),
                                     Token(simple_ty, "[")])
                        cs.next()
                        continue
                    files = cs.scan_package_filenames()
                    i = 0
                    while i < len(files):  # process private packages
                        file = files[i]
                        p = file.rfind("-private")
                        if p < 0 or not len(file) - len("-private") == p:
                            i += 1
                            continue
                        defs_db_file = file+".db"
                        self.add_defs(file)
                        del files[i:(i+1)]
                    if files: # non-private packages left
                        group_content = ",".join(files)
                        to_add_str = "\\usepackage{%s}" % (group_content)
                        to_add = tokenize(to_add_str)
                        text.extend(to_add)
                else:
                    if isletter(name[0], isatletter):
                        token = Token(esc_str_ty, name)
                    else:
                        token = Token(esc_symb_ty, name)
                    text.append(token)
                    if "makeatletter" == name:
                        isatletter=True
                    elif "makeatother" == name:
                        isatletter=False
        self.reset()
        return self.data

    def smart_detokenize(self):
        r"""
        Output is a string.
        If the list contains an \input{file} then the content of file
        file-clean.tex replaces it in the output.
        """
        self.reset()
        if not self.legal():
            return ""
        out = ""
        previtem = None
        while self.uplegal():
            item = self.item
            """Insert a separating space after an escape sequence if it is a
            string and is followed by a letter."""
            if (None != previtem and esc_str_ty == previtem.type
                and simple_ty == item.type and isletter(item.val[0], False)):
                out += " "
            previtem = item
            if not (esc_str_ty == item.type and "input" == item.val):
                out += item.show()
                self.next()
            else:
                self.next()
                group = self.scan_group()
                file = detokenize(group.val)
                clean_file = "%s-clean.tex" % (file)
                print("Reading file %s" % (clean_file))
                fp = open(clean_file,"r")
                content = fp.read()
                fp.close()
                out += content
        return out

    # Basic tex scanning

    def skip_blank_tokens(self): # we also skip comment tokens.
        item = self.item
        while (self.uplegal() and
               (comment_ty == item.type or
                (simple_ty == item.type and blank_re.match(item.val)))):
            item = self.next()
        return item

    def scan_group(self):
        """Returns group.
        """
        if not self.legal():
            raise ParsingError("No group to scan.")
        item = self.item
        if not (simple_ty == item.type and "{" == item.val):
            return Group(token_ty, [self.item])
        count = 1
        group = []
        item = self.next()
        while count and self.uplegal():
            if simple_ty == item.type:
                if "{" == item.val:
                    count += 1
                elif "}" == item.val:
                    count -= 1
            if count != 0:
                group.append(item)
            item = self.next()
        return Group(group_ty, group)

    # Command and environment definitions

    def scan_command_name(self):
        """Returns name.
        """
        if not self.legal():
            raise ParsingError("No command name to scan.")
        item = self.item
        name = ""
        if item.type in [esc_symb_ty, esc_str_ty]:
            name = item.val
        else:
            if not "{" == item.val:
                raise ParsingError("Command definition misses first {.")
            self.next()
            item = self.skip_blank_tokens()
            if not item.type in [esc_symb_ty, esc_str_ty]:
                raise ParsingError("Command definition does not begin with "
                                   "control sequence.")
            name = item.val
            self.next()
            item = self.skip_blank_tokens()
            if not "}" == item.val:
                raise ParsingError(f"Definition for commmand {name} misses "
                                   f"first }}., {item.val}")
        self.next()
        self.skip_blank_tokens()
        return name

    def scan_numargs(self, name):
        """
        name is the name of the command or environment definition being
        scanned.
        Starts on a nonblank token.
        Returns numargs
        where numargs is the number of arguments in a command or environment
        definition,
        """
        if not self.legal():
            raise ArgumentError("No numargs to scan.")
        item = self.item
        numargs = 0
        if not simple_ty == item.type:
            raise ValueError("Illegal command or environment definition: "+name)
        if "[" == item.val:
            if not 4 < len(self.data):
                raise ParsingError(
                    "Command or environment definition is illegal: "+name)
            item = self.next()
            if not simple_ty == item.type:
                raise ParsingError(
                    "Illegal command or environment definition: "+name)
            numargs = item.val
            if not pos_digit_re.match(numargs):
                raise ParsingError("{} must be argument number after {}"
                                   .format(numargs, name))
            numargs = int(numargs)
            self.next()
            item = self.skip_blank_tokens()
            if not simple_ty == item.type:
                raise ParsingError("Illegal command definition: "+name)
            if "]" != item.val:
                raise ParsingError("Illegal command definition: "+name)
            self.next()
            self.skip_blank_tokens()
        return numargs

    def scan_command_def(self):
        """Scan a command definition.
        Return command_def.
        Assumes that the number of arguments is at most 9.
        """
        if not self.legal():
            raise ParsingError("No command definition to scan.")
        item = self.item
        if not 2 < len(self.data):
            raise ParsingError("Command definition is illegal.")
        # newcommand or renewcommand
        if not item.type in [esc_symb_ty, esc_str_ty]:
            raise ParsingError("Command definition should begin with control "
                               "sequence: "+item.val)
        if item.val not in ["newcommand", "renewcommand"]:
            raise ParsingError("Command definition should begin with control "
                               "sequence.")
        self.next()
        self.skip_blank_tokens()

        cmd_name = self.scan_command_name()
        numargs = self.scan_numargs(cmd_name)

        body_group = self.scan_group()
        if group_ty != body_group.type:
            raise ParsingError("Command body missing: "+cmd_name)
        body_val = strip_comments(body_group.val)
        return Command_def(cmd_name, numargs, body_val)

    def scan_env_name(self):
        """Starts on a {.
        Returns name.
        """
        if not self.legal():
            raise ParsingError("No environment name to scan.")
        item = self.item
        if not "{" == item.val:
            raise ParsingError("Env. definition begins with {}, not with {"
                               .format(item.val))
        self.next()
        item = self.skip_blank_tokens()
        name = ""
        if not simple_ty == item.type:
            raise ParsingError("1. Env. def. begins with cont. seq. {}, not "
                               "with env.name.".format(item.val))
        while self.uplegal() and not blank_or_rbrace_re.match(item.val):
            name += item.val
            item = self.next()
            if not simple_ty == item.type:
                raise ParsingError("2. Env. def. begins with cont. seq. {}, "
                                   "not with env.name.".format(item.val))
        item = self.skip_blank_tokens()
        if not "}" == item.val:
            raise ParsingError("Command definition does not begin with "
                               "control sequence.")
        self.next()
        self.skip_blank_tokens()
        return name

    def scan_env_def(self):
        """Scan an environment definition.
        Return env_def
        Assumes that the number of arguments is at most 9.
        """
        if not self.legal():
            raise ParsingError("No environment definition to scan.")
        item = self.item
        if not 7 < len(self.data):
            raise ParsingError("Environment definition is illegal.")
        pos = 0

        if not item.type in [esc_symb_ty, esc_str_ty]:
            raise ParsingError("Env. definition does not begin with control "
                               "sequence: "+item.val)
        if item.val not in ["newenvironment", "renewenvironment"]:
            raise ParsingError("Env. definition does not begin with control "
                               "sequence.")
        self.next()
        self.skip_blank_tokens()

        env_name = self.scan_env_name()
        numargs = self.scan_numargs(env_name)
        self.skip_blank_tokens()

        begin_group = self.scan_group()
        if group_ty != begin_group.type:
            raise ParsingError("Begin body missing: "+env_name)
        begin_val = strip_comments(begin_group.val)

        self.skip_blank_tokens()

        end_group = self.scan_group()
        if group_ty != end_group.type:
            raise ParsingError("End body missing:"+env_name)
        end_val = strip_comments(end_group.val)

        return Env_def(env_name, numargs, begin_val, end_val)

    def scan_defs(self):
        if not self.legal():
            raise ParsingError("No definitions to scan.")
        self.reset()
        command_defs, env_defs = self.defs
        while self.uplegal():
            if (esc_str_ty == self.item.type
                and self.item.val in ["newcommand", "renewcommand"]):
                command_def = self.scan_command_def()
                command_defs[command_def.name] = command_def
            elif (esc_str_ty == self.item.type and self.item.val
                  in ["newenvironment", "renewenvironment"]):
                env_def = self.scan_env_def()
                env_defs[env_def.name] = env_def
            else:
                self.next()

    # Instances

    def scan_args(self, command_or_env_def):
        """Scan the arguments of a command or environment.
        Return [args].
        """
        if not self.legal():
            raise ParsingError("No arguments to scan.")
        numargs = command_or_env_def.numargs
        name = command_or_env_def.name

        args = []
        for i in range(numargs):
            arg = []
            if not (simple_ty == self.item.type and "{" == self.item.val):
                arg = [self.item]
                self.next()
            else:
                group = self.scan_group()
                arg = group.val
            args.append(arg)
        return args

    def scan_command(self, command_def):
        """Scan the arguments of a command.
        Return command_instance
        """
        if not self.legal():
            raise ParsingError("No command to scan.")
        if not self.item.type in [esc_symb_ty, esc_str_ty]:
            raise ParsingError("Command does not begin with control sequence.")
        name = self.item.val
        self.next()
        if 0 < command_def.numargs:
            self.skip_blank_tokens()
            args = self.scan_args(command_def)
        else:
            args = []
        return Command_instance(name, args)

    def test_env_boundary(self, item):
        r"""Check whether an environment begin or end follows.
        Return 1 if \begin, -1 if \end, 0 otherwise.
        """
        d = 0
        if esc_str_ty == item.type:
            if "begin"==item.val:
                d = 1
            elif "end"==item.val:
                d = -1
        return d

    def scan_env_begin(self):
        """Scan an environment name.
        Return env_name.
        """
        if not self.legal():
            raise ParsingError("No environment begin to scan.")
        item = self.item
        if not (esc_str_ty == item.type and "begin" == item.val):
            raise ParsingError("Environment does not begin with begin.")
        self.next()
        name_group = self.scan_group()
        name = detokenize(name_group.val)
        return name

    def scan_env_end(self):
        """Scan an environment end.
        Return env_name.
        """
        if not self.legal():
            raise ParsingError("No environment end to scan.")
        item = self.item
        if not (esc_str_ty == item.type and "end" == item.val):
            raise ParsingError("Environment does not end with end.")
        self.next()
        name_group = self.scan_group()
        name = detokenize(name_group.val)
        return name

    def scan_env_rest(self, env_def):
        r"""Scanning starts after \begin{envname}.
        Returns env_instance.
        """
        if not self.legal():
            raise ParsingError("No environment rest to scan.")
        count = 1 # We are already within a boundary.
        args = self.scan_args(env_def)
        body = []
        while count and self.uplegal():
            old_pos = self.pos
            d = self.test_env_boundary(self.item)
            count += d
            if 1 == d:
                self.scan_env_begin()
            elif -1 == d:
                self.scan_env_end()
            else:
                self.next()
            if 0 < count:
                body.extend(self.data[old_pos : self.pos])
        return Env_instance(env_def.name, args, body)

    # Definitions

    def restore_defs(self):
        if os.path.isfile(self.defs_db_file):
            print("Using defs db %s" % (self.defs_db_file))
            db_h = shelve.open(self.defs_db)
            self.defs = db_h["defs"]
            db_h.close()

    def save_defs(self):
        db_h = shelve.open(self.defs_db)
        if "defs" in db_h:
            del db_h["defs"]
        db_h["defs"] = self.defs
        db_h.close()

    def add_defs(self, defs_file):
        defs_file_compl = defs_file + ".sty"
        if not os.path.isfile(defs_file_compl):
            raise FileNotFoundError("%s does not exist" % (defs_file_compl))

        defs_db_file = self.defs_db_file
        if newer(defs_db_file, defs_file_compl):
            print("Using defs db %s for %s" % (defs_db_file, defs_file))
        else:
            defs_fp = open(defs_file_compl, "r")
            defs_str = defs_fp.read()
            defs_fp.close()
            ds = Tex_stream()
            ds.defs = self.defs
            defs_text = ds.smart_tokenize(defs_str)
            # changing ds.defs will change self.defs
            if self.debug:
                defs_seen_file = "%s-seen.sty" % (defs_file)
                defs_seen_fp = open(defs_seen_file, "w")
                out = detokenize(defs_text)
                defs_seen_fp.write(out)
                defs_seen_fp.close()
            ds.scan_defs()
            if self.debug:
                out = ""
                command_defs, env_defs = self.defs
                for def_name in command_defs.keys():
                    out += command_defs[def_name].show() + "\n"
                for def_name in env_defs.keys():
                    out += env_defs[def_name].show() +"\n"
                print("Definitions after reading %s:" % (defs_file))
                print(out)

    # Applying definitions, recursively
    # (maybe not quite in Knuth order, so avoid tricks!)

    def subst_args(self, body, args):
        out = []
        pos = 0
        while pos < len(body):
            item = body[pos]
            if not (simple_ty == item.type and "#" == item.val):
                out.append(item)
                pos += 1
                continue
            pos += 1
            token = body[pos]
            argnum = token.val
            if not pos_digit_re.match(argnum):
                raise ArgumentError("# is not followed by number.")
            argnum = int(argnum)
            if argnum > len(args):
                raise ArgumentError("Too large argument number.")
            arg = args[argnum-1]
            out += arg
            pos += 1
        return out

    def apply_command_recur(self, command_instance):
        command_defs, env_defs = self.defs
        name = command_instance.name
        command_def = command_defs[name]

        args = command_instance.args
        body = command_def.body
        result = self.subst_args(body, args)
        try:
            result = self.apply_all_recur(result)
        except Empty_text_error as e:
            raise RuntimeError("apply_all_recur fails on command instance {}: "
                               "{}, {}".format(command_instance.show(),
                                               detokenize(e.data), e.message))
        return result

    def apply_env_recur(self, env_instance):
        command_defs, env_defs = self.defs
        name = env_instance.name
        env_def = env_defs[name]

        begin, end = env_def.begin, env_def.end
        body, args = env_instance.body, env_instance.args
        out = self.subst_args(begin, args) + body + self.subst_args(end, args)
        return self.apply_all_recur(out)


    def apply_all_recur(self, data, report=False):
        ts = Tex_stream(data)
        ts.defs = self.defs
        command_defs, env_defs = self.defs
        out = []
        progress_step = 10000
        progress = progress_step
        if not ts.legal():
            raise Empty_text_error(data, "No text to process.")
        while ts.uplegal():
            if self.pos > progress:
                if report:
                    print(self.pos)
                progress += progress_step
            if not ts.item.type in [esc_symb_ty, esc_str_ty]:
                out.append(ts.item)
                ts.next()
                continue
            if 1 == ts.test_env_boundary(ts.item):
                old_pos = ts.pos
                env_name = ts.scan_env_begin()
                if env_name not in env_defs:
                    out.extend(ts.data[old_pos : ts.pos])
                    continue
                else:
                    env_def = env_defs[env_name]
                    env_instance = ts.scan_env_rest(env_def)
                    result = ts.apply_env_recur(env_instance)
                    out.extend(result)
            elif ts.item.val not in command_defs:
                out.append(ts.item)
                ts.next()
                continue
            else:
                command_def = command_defs[ts.item.val]
                command_inst = ts.scan_command(command_def)
                result = ts.apply_command_recur(command_inst)
                out.extend(result)
        return out


    # Processing files

    def process_file(self, file):
        """Returns the new defs.
        """
        file = cut_extension(file, ".tex")
        source_file = "%s.tex" % (file)
        print("File %s [" % (source_file))
        source_fp = open(source_file, "r")
        text_str = source_fp.read()
        source_fp.close()

        self.smart_tokenize(text_str, handle_inputs=True)
        if not self.data:
            raise RuntimeError("Empty tokenization result.")
        self.reset()

        if self.debug:
            source_seen_fname = "%s-seen.tex" % (file)
            source_seen_fp = open(source_seen_fname, "w")
            source_seen_fp.write(detokenize(self.data))
            source_seen_fp.close()

        self.data = self.apply_all_recur(self.data, report=True)

        result_fname = "%s-clean.tex" % (file)
        print("Writing %s [" % (result_fname))
        result_fp = open(result_fname, "w")
        result_fp.write(self.smart_detokenize())
        result_fp.close()
        print("] file %s" % (result_fname))
        print("] file %s" % (source_file))

    def process_if_newer(self, file):
        r"""
        \input{file} is be added to the token list.
        If the input file is newer it is processed.
        Returns tokenized \input{file}.
        """
        file = cut_extension(file, ".tex")
        tex_file = file+".tex"
        clean_tex_file = file+"-clean.tex"
        if newer(clean_tex_file, tex_file):
            print("Using %s." % (clean_tex_file))
        else:
            ts = Tex_stream()
            ts.data = []
            ts.defs = self.defs
            ts.process_file(file)
        to_add = "\\input{%s}" % (file)
        return tokenize(to_add)

def _rename_figures(renamestr, maintex, extensions=None, start=1):
    """This function added by Alexandre René."""
    maintex = Path(maintex)
    if extensions is not None:
        if isinstance(extensions, str):
            extensions = extensions.split(',')
        extensions = ['.'+e.strip(' .') for e in extensions]
    root = maintex.stem
    os.chdir(maintex.parent)
    siblings = os.listdir()
    if '{' in renamestr and '}' in renamestr:
        # Passing an invalid substitution string prevents figure renaming
        if str(root).endswith('-clean'):
            cleanroot = Path(root).with_suffix('.tex')
        else:
            cleanroot = Path(str(root) + "-clean.tex")
        renamedroot = cleanroot.with_suffix(".renamed.tex")
        if not cleanroot.exists():
            raise FileNotFoundError(f"Could not find the file {cleanroot}.")
        regex = re.compile(r"\\includegraphics(\[.*\])?\{(.*)\}")
        with open(cleanroot, 'r') as f:
            tex = f.read()
        tokens = []
        pos = 0
        i = start
        for match in regex.finditer(tex):
            # The match returns two groups:
            #   First group is the optional argument, which we can ignore
            #   Second group is the filename, which we need
            #   (group '0' is the entire match)
            origstem = match.group(2)
            origfiles = [Path(fname) for fname in siblings
                         if origstem in fname]
            if len(origfiles) == 0:
                warn("The figure reference {} was not renamed because it does "
                     "not point to an existing file.".format(origstem))
                continue
            newstem = renamestr.format(i)
            # If there is a period in the stem we need to include the extension
            texlink = newstem
            if '.' in texlink or extensions is not None:
                if extensions is None:
                    raise ValueError(
                    "Your renamed figure files have non-extension periods in "
                    "their filenames. Because of this their extension needs to "
                    "be specified in the TeX source, and for this you need to "
                    "specify a preference order for extensions with the "
                    "`extensions` option.")
                fileexts = [p.suffix for p in origfiles]
                filefound = False
                for ext in extensions:
                    if ext in fileexts:
                        texlink = str(texlink) + ext
                        filefound = True
                        break
                if not filefound:
                    raise FileNotFoundError(
                        "No file with appropriate extension was found to "
                        f"match {newstem}")

            # Update the TeX. start(2) returns the starting index of 2nd group)
            tokens.extend([tex[pos:match.start(2)], texlink])
            pos = match.end(2)

            #tex = tex[:match.start(2)] + newstem + tex[match.end(2):]
            # print()
            # print(tex[match.start(2)-10:match.start(2)])
            # print(tex[match.end(2):match.end(2)+10])
            # Move the image files
            for ofile in origfiles:
                # Note: newstem may contain 'suffixes' which need to be kept
                # (e.g. NECO asks for the format Figure.1.eps, …)
                nfile = Path(newstem + ofile.suffix)
                ofile.replace(nfile)
            i += 1
        tokens.append(tex[pos:])
        with open(renamedroot, 'w') as f:
            f.write(''.join(tokens))

# Main
@click.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--defs', default=None, type=click.File('r'))
@click.option('--renamefigs', default="figure_{}",
              help="Rename figures sequentially. Brackets are substituted by "
                   "the figure number with Python's `format` method, and the "
                   "appropriate extension is added to the file name. Pass an "
                   "empty string to prevent renaming figures.")
@click.option('--figexts', default=None,
              help="Define an order of preference for figure extensions; "
                   "pass multiple values by separating them with commas. "
                   "This will fix the file extension in the TeX source. "
                   "(Generally not recommended, but sometimes required.)")
@click.argument('maintex', type=click.Path(exists=False,
                                           file_okay=True, dir_okay=False))
@click.argument('outputdir', type=click.Path(exists=False,
                                             file_okay=False, dir_okay=True),
                default="flat-latex")
def main(maintex, outputdir, renamefigs, figexts, debug, defs):

    # flap_output_dir = Path("_tmp_expand_macros/")
    flap_output_dir = Path(outputdir)
    flap_merged_filename = "merged.tex"

    # First use flap to flatten the latex into a single file
    print("Merging files with FLaP...")
    os.makedirs(flap_output_dir, exist_ok=True)
    flap.ui.Controller(
        flap.ui.OSFileSystem(),
        flap.ui.Display(sys.stdout, verbose=False)
        ).run(maintex, str(flap_output_dir))

    # Now run the ported de-macro code
    print("Expanding macros...")
    root = flap_output_dir/flap_merged_filename
    root = cut_extension(str(root), ".tex")
    # if "--defs" in options:
    #     defs_root = options["--defs"]
    if defs is not None:
        defs_root = defs
    else:
        defs_root = "%s" % (root)
    defs_db = defs_root
    defs_db_file = defs_root+".db"

    ts = Tex_stream()
    ts.defs_db = defs_db
    ts.defs_db_file = defs_db_file
    ts.debug = debug

    ts.restore_defs()
    ts.process_file(root)
    # for root in restargs:
    #     ts.process_file(root)

    print("(Re)creating defs db %s" % (defs_db))
    ts.save_defs()
    del ts  # We are done with de-macro; free the associated memory

    # Replace figure names
    _rename_figures(renamefigs, root, extensions=figexts)

@click.command()
@click.option('--renamestr', type=str, default='figure_{}')
@click.option('--start', type=int, default=1,
              help="Start numbering figures with this value.")
@click.option('--figexts', default=None,
              help="Define an order of preference for figure extensions; "
                   "pass multiple values by separating them with commas. "
                   "This will fix the file extension in the TeX source. "
                   "(Generally not recommended, but sometimes required.)")
@click.argument('maintex', type=click.Path(exists=True, file_okay=True, dir_okay=False))
def rename_figures(renamestr, maintex, start, figexts):
    return _rename_figures(renamestr, maintex, extensions=figexts, start=start)

@click.command()
@click.option('--format', type=click.Choice(['pdf', 'eps'], case_sensitive=False), default='pdf')
@click.option('--in-place/--not-in-place', default=False,
              help="Change image files in place. This should be safe to use "
                   "on the directory produced by 'expand-latex-macros'; "
                   "otherwise be careful not to clobber your original files.\n"
                   "By default, files are placed in a subdirectory '_cmyk'.")
@click.option('--overwrite/--no-overwrite', default=True,
              help="Use --no-overwrite to prevent overwriting files in the "
                   "_cmyk subdirectory. Default: --overwrite.")
@click.option('--exclude', type=str, default=None,
              help="Files to exclude (such as the compiled pdf document). "
                   "This is required if 'format' is 'pdf'. To pass multiple "
                   "filenames, separate them with commas.")
@click.option('--echo/--no-echo',
              help="Print the command to console instead of executing it. "
                   "It's a good idea to run the script with this option first.")
@click.argument('srcdir',
                type=click.Path(exists=True, file_okay=False, dir_okay=True),
                default='flat-latex')
# The following values should generally be fine as-is
@click.option('--dAutoRotatePages',         type=str, default='/None', help='Default: /None')
@click.option('--dEmbedAllFonts',           type=str, default='true', help='Default: true')
@click.option('--sColorConversionStrategy', type=str, default='CMYK', help='Default: CMYK')
@click.option('--dAutoFilterColorImages',   type=str, default='false', help='Default: false')
@click.option('--dAutoFilterGrayImages',    type=str, default='false', help='Default: false')
@click.option('--dColorImageFilter',        type=str, default='/FlateEncode',
              help='Default: /FlateEncode (lossless image conversion). Ignored for EPS, because '
              'with gs v9.27 causes conversion to fail.')
@click.option('--dGrayImageFilter',         type=str,
              help='Default: /FlateEncode (lossless image conversion). Ignored for EPS, because '
              'with gs v9.27 causes conversion to fail.')
@click.option('--dDownsampleMonoImages',    type=str, default='false', help='Default: false')
@click.option('--dDownsampleGrayImages',    type=str, default='false', help='Default: false')
def convert_to_cmyk(format, in_place, overwrite, exclude, echo, srcdir, **kwargs):
    """
    Tested with ghostscript v9.27. © Alexandre René 2020.

    This function wraps a ghostscript call which converts all image files in
    the source directory to a CMYK colour scheme. It's based on the command
    described here: http://zeroset.mnim.org/2014/07/14/save-a-pdf-to-cmyk-with-inkscape/.
    Ghostscript is usually installed by default on Linux; for Windows or
    macOS it will first need to be installed.

    A typical call may look like

    $ convert-to-cmyk --format pdf --exclude flat-latex/main.pdf --in-place flat-latex

    where 'flat-latex' is the directory where 'expand-latex-macros' placed
    its output. The most relevant options are

      --format
      --exclude
      --in-place
      --echo

    Other options are passed directly to ghostscript, and follow its (or
    rather Adobe's) rather arcane naming scheme.

    More examples:

    To check the command before execution:

    $ convert-to-cmyk --format eps --echo --in-place flat-latex

    To avoid overwriting the original image files:

    $ convert-to-cmyk --format eps flat-latex

    Where to find more information on the distiller options
    -------------------------------------------------------

    - The ghostscript documentation [1] should be the first place to look.

    - The ghostscript options closely follows those of the Adobe Distiller [2].

    Hacks / Changes compared to the blog post on zeroset
    ----------------------------------------------------

    - With v9.27 of ghostscript, I found that setting the ImageFilter option
      with EPS export causes a generic error (possibly unrecognized option).
      Since turning off AutoFilter[Color|Gray]Images should set the filter to
      lossless anyway (according to the Adobe Distiller documentation [2]),
      the function just ignores these options when exporting to EPS.

    - The 'ProcessColorModel' option is remove since it's been deprecated.

    Troubleshooting
    ---------------

    - Why is the resulting image cropped ?

    The EPS writer will always limit the output to the size of the page. Make
    sure the stated dimensions of your original file aren't too large.
    (One way to view/change dimensions: in Inkscape, File->Document Properties.)

    - What do this error mean ?

    `Unrecoverable error: rangecheck in .putdeviceprops`

    As far as I can tell this is a generic ghostscript error; I've encountered
    it because of misformed argument names or values.
    (remember that arguments names and values are case-sensitive)

    References
    -----------

    - [1] https://www.ghostscript.com/doc/9.27/VectorDevices.htm

    - [2] https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/PDFCreationSettings_v9.pdf

    """
    import subprocess
    # Fixed flags
    flags = ["-dSAFER",    # Recommend for all batch scripts; prevents opening/running external files
             "-dBATCH",    # Don't launch the gs console
             "-dNOPAUSE",  # Don't stop and wait for input at the end.
             "-q"          # Don't print the copyright notice on every call
             ]
    # gs flags are all converted to lowercase; we need to convert them back to
    # CamelCase
    gsflagnames = ['dAutoRotatePages',
                   'dEmbedAllFonts',
                   'sColorConversionStrategy',
                   'dProcessColorModel',
                   'dAutoFilterColorImages',
                   'dAutoFilterGrayImages',
                   'dColorImageFilter',
                   'dGrayImageFilter',
                   'dDownsampleMonoImages',
                   'dDownsampleGrayImages']
    gsflagnameslc = [s.lower() for s in gsflagnames]
    for k in list(kwargs.keys()):  # list() creates an copy that won't change during iteration
        # Retrieve the CamelCase flagname
        kcc = '-' + gsflagnames[gsflagnameslc.index(k)]
        # Replace entry in kwargs with the CamelCase key
        assert kcc not in kwargs
        kwargs[kcc] = kwargs[k]
        del kwargs[k]

    # Parse the 'exclude' option
    if format=='pdf' and exclude is None:
        raise ValueError("You must specify excluded files if your images are "
                         "in PDF format. If none are to be excluded, you can "
                         "provide an empty string.")
    if exclude is None:
        exclude = []
    else:
        exclude = [Path(p) for p in exclude.split(',') if p != ""]

    # Determine the extension of the image files
    if format=='pdf':
        suffix='.pdf'
        kwargs['-sDEVICE'] = 'pdfwrite'
    elif format=='eps':
        suffix='.eps'
        kwargs['-sDEVICE'] = 'eps2write'
        kwargs.pop('-dColorImageFilter')
        kwargs.pop('-dGrayImageFilter')
    else:
        raise AssertionError  # Should not be possible to reach here

    flags += [f"{k}={v}" for k,v in kwargs.items()]

    # Determine the output directory
    # ==> ghostscript conversion cannot be done in-place, so for 'in-place'
    #     we still put files in _cmyk subdir, and move afterwards
    srcdir = Path(srcdir)
    outdir = srcdir/"_cmyk"
    if not echo and not overwrite and outdir.exists():
        raise RuntimeError(
            "You asked not to overwrite files, but the '_cmyk' already "
            "exists. Either delete the directory or allow for overwriting.")
    elif not echo:
        os.makedirs(outdir, exist_ok=overwrite)

    # Loop over the image files
    filenames = [f for f in os.listdir(srcdir) if Path(f).suffix == suffix]
    for filename in filenames:
        inpath = str(srcdir/filename)
        outpath = str(outdir/filename)
        cmdlst = ["gs"] + flags + [f'-sOutputFile={outpath}', inpath]
        if echo:
            print(' '.join(cmdlst))
            if len(filenames) > 1:
                print("Only the first command was printed. It would be "
                      f"applied to the following {len(filenames)} files:")
                print("\n".join(filenames))
                break
        else:
            print(f"Processing {filename}...")
            subprocess.run(cmdlst)
            if in_place:
                # Move processed file on top of original
                Path(outpath).replace(inpath)

if __name__ == "__main__":
    main()
